import os
import re # Uso le espressioni regolari per estrarre comandi nascosti dal testo dell'IA
from dotenv import load_dotenv 
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_mongodb import MongoDBChatMessageHistory
from pymongo import MongoClient

# Inizializzo le variabili d'ambiente prima di fare qualsiasi altra cosa
load_dotenv()

# --- COSTANTI DI CONFIGURAZIONE ---
DB_NAME = "abisso_db"
COLLECTION_NAME = "chat_history"
STATE_COLLECTION = "game_state" # La nuova collezione dedicata allo stato del giocatore
MODEL_NAME = "meta-llama/Meta-Llama-3-8B-Instruct"

class AbissoEngine:
    """
    Questa classe gestisce l'intera logica di backend. 
    L'ho strutturata così per separare il 'cervello' del gioco dall'interfaccia utente (Streamlit).
    """
    def __init__(self):
        # 1. RECUPERO LE CREDENZIALI (Metodo Bulletproof)
        self.api_key = os.getenv("H2O_API_KEY")
        self.mongo_uri = os.getenv("MONGO_URI")
        
        # Se os.getenv fallisce (siamo su Streamlit Cloud), usiamo st.secrets
        if not self.api_key or not self.mongo_uri:
            try:
                import streamlit as st
                self.api_key = st.secrets["H2O_API_KEY"]
                self.mongo_uri = st.secrets["MONGO_URI"]
            except Exception:
                pass # Ignoriamo l'errore qui, ci pensa il blocco sotto a bloccare tutto

        # Controllo finale
        if not self.api_key:
            raise ValueError("🚨 ERRORE: Manca H2O_API_KEY!")
        if not self.mongo_uri:
            raise ValueError("🚨 ERRORE: Manca MONGO_URI!")

        # 2. Connessione diretta a MongoDB
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[DB_NAME]
        self.state_db = self.db[STATE_COLLECTION] 

        # 3. INIZIALIZZO L'IA (Puntando ai server di H2O Enterprise)
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url="https://h2ogpte.genai.h2o.ai/v1", # <--- Il nuovo "indirizzo" del cervello
            model=MODEL_NAME,
            temperature=0.7 
        )

        # --- 3. PROMPT ENGINEERING AVANZATO (Context Injection & Output Parsing) ---
        # Per risolvere il problema dell'IA che 'dimentica' il database, uso la 'Context Injection':
        # Inietto la variabile {inventario} direttamente nel System Prompt ad ogni turno.
        # Inoltre, istruisco l'IA a usare dei 'codici' che io potrò intercettare col Python.
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "Sei un Dungeon Master spietato per un gioco di ruolo horror.\n"
                       "ATTENZIONE - INVENTARIO DEL GIOCATORE: {inventario}\n"
                       "Il giocatore possiede SOLO questi oggetti. Non fargli usare cose che non ha.\n\n"
                       "REGOLE DI SISTEMA PER L'INVENTARIO:\n"
                       "Se il giocatore trova, ruba o riceve un nuovo oggetto, devi scrivere alla fine della tua risposta esattamente: [ADD: NomeOggetto]\n"
                       "Se il giocatore perde, usa, o gli viene distrutto un oggetto, scrivi: [REMOVE: NomeOggetto]\n\n"
                       "Descrivi l'ambiente usando i 5 sensi. Termina chiedendo: 'Cosa fai?'"),
            MessagesPlaceholder(variable_name="history"), # Qui LangChain mette la vecchia chat
            ("human", "{input}")
        ])

        self.chain = self.prompt | self.llm
        
        # 4. Assemblo l'agente collegandolo a MongoDB per la cronologia chat
        self.agent_with_memory = RunnableWithMessageHistory(
            self.chain,
            self._get_mongo_history, 
            input_messages_key="input",
            history_messages_key="history"
        )

    def _get_mongo_history(self, session_id: str):
        """Metodo privato per la persistenza della chat."""
        return MongoDBChatMessageHistory(
            connection_string=self.mongo_uri,
            session_id=session_id,
            database_name=DB_NAME,
            collection_name=COLLECTION_NAME,
        )
    
    # --- METODI PER GESTIRE LO STATO (CRUD su Database) ---
    def get_inventory(self, session_id: str) -> list:
        """Legge l'inventario dal DB. Se la partita è nuova, lo crea."""
        stato_partita = self.state_db.find_one({"session_id": session_id})
        
        # Se trovo il documento e ha il campo 'inventory', lo restituisco
        if stato_partita and "inventory" in stato_partita:
            return stato_partita["inventory"]
        else:
            # Altrimenti creo il setup di base per questo utente
            inventario_base = ["Fiammiferi", "Chiave arrugginita"]
            self.state_db.update_one(
                {"session_id": session_id},
                {"$set": {"inventory": inventario_base}},
                upsert=True # Upsert = Insert + Update (se non c'è crealo, se c'è aggiornalo)
            )
            return inventario_base

    def _modifica_inventario_db(self, session_id: str, azione: str, oggetto: str):
        """Metodo privato per aggiornare l'array nel database senza ricaricare tutto."""
        if azione == "ADD":
            self.state_db.update_one({"session_id": session_id}, {"$push": {"inventory": oggetto}})
        elif azione == "REMOVE":
            self.state_db.update_one({"session_id": session_id}, {"$pull": {"inventory": oggetto}})

    # --- IL CORE LOOP DELL'AGENTE ---
    def esegui_turno(self, input_utente: str, session_id: str):
        """
        Il metodo pubblico. Riceve l'azione del giocatore, inietta lo stato, 
        interroga l'IA, intercetta i comandi e restituisce la risposta pulita.
        """
        try:
            # 1. PREPARAZIONE: Leggo cosa ha in tasca l'utente in questo momento
            inventario_lista = self.get_inventory(session_id)
            inventario_str = ", ".join(inventario_lista) if inventario_lista else "Vuoto (non hai nulla)"

            # 2. ESECUZIONE: Invio il prompt compilato con le variabili aggiornate
            risposta = self.agent_with_memory.invoke(
                {"input": input_utente, "inventario": inventario_str},
                config={"configurable": {"session_id": session_id}}
            )
            testo_ia = risposta.content

            # 3. INTERCETTAZIONE: Uso le regex per cercare i tag [ADD: ...] e [REMOVE: ...]
            # Se l'IA ha stampato quei codici, Python li cattura in queste due liste
            aggiunte = re.findall(r'\[ADD:\s*(.*?)\]', testo_ia)
            rimozioni = re.findall(r'\[REMOVE:\s*(.*?)\]', testo_ia)

            # Eseguo i comandi sul database per ogni oggetto trovato
            for oggetto in aggiunte:
                self._modifica_inventario_db(session_id, "ADD", oggetto)
            for oggetto in rimozioni:
                self._modifica_inventario_db(session_id, "REMOVE", oggetto)

            # 4. PULIZIA: Cancello i codici 'tecnici' dalla stringa per non rompere l'immersione del giocatore
            testo_pulito = re.sub(r'\[ADD:\s*.*?\]', '', testo_ia)
            testo_pulito = re.sub(r'\[REMOVE:\s*.*?\]', '', testo_pulito)

            # Restituisco la storia pulita a Streamlit
            return testo_pulito.strip()

        except Exception as e:
            return f"[Errore di Sistema - L'Abisso è corrotto]: {e}"

# --- INIZIALIZZAZIONE GLOBALE ---
# Istanzio il motore in modo che Streamlit possa importarlo già pronto
engine = AbissoEngine()

INCIPIT = "Ti svegli sul pavimento freddo di una stanza di pietra. Senti l'odore metallico del sangue secco. Non c'è luce. Cosa fai?"

# Wrapper pulito, rimosso l'ID fisso. Ora session_id è obbligatorio
def gioca_turno(messaggio_utente, session_id):
    return engine.esegui_turno(messaggio_utente, session_id)

# --- BLOCCO DI TEST PER TERMINALE ---
if __name__ == "__main__":
    import uuid
    # Se lancio il file da terminale, genero un ID al volo per testare il salvataggio
    id_test = f"test_{str(uuid.uuid4())[:4]}"
    print(f"💀 ENGINE AVVIATO (TEST MODE) - ID: {id_test} 💀\n[DM]: {INCIPIT}")
    
    while True:
        azione = input("\n[Tu]: ")
        if azione.lower() in ["esci", "quit"]: break
        print(f"\n[DM]: {gioca_turno(azione, id_test)}")