import os
from dotenv import load_dotenv 
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_mongodb import MongoDBChatMessageHistory
from pymongo import MongoClient # <--- IMPORT PER GESTIRE LO STATO

# Carico le variabili d'ambiente.
load_dotenv()

# --- CONFIGURAZIONE GLOBALE ---
DB_NAME = "abisso_db"
COLLECTION_NAME = "chat_history"
STATE_COLLECTION = "game_state" # <--- Corretto il nome
MODEL_NAME = "llama-3.3-70b-versatile"

class AbissoEngine:
    """
    In questa classe ho racchiuso il 'Cervello' del Dungeon Master. 
    L'ho strutturata così per isolare le responsabilità.
    """
    
    def __init__(self):
        # Recupero le credenziali.
        self.api_key = os.getenv("GROQ_API_KEY")
        self.mongo_uri = os.getenv("MONGO_URI")
        
        # Validation check
        if not self.api_key or not self.mongo_uri:
            raise ValueError("Mancano le configurazioni ambientali (API Key o Mongo URI)")

        # --- CONNESSIONE DIRETTA A MONGODB PER LO STATO  ---
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[DB_NAME]
        self.state_db = self.db[STATE_COLLECTION] 

        # 1. Configurazione del Modello (LLM)
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
            model=MODEL_NAME,
            temperature=0.7 
        )

        # 2. Il Prompt Template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "Sei un Dungeon Master spietato e inquietante per un gioco di ruolo horror psicologico.\n"
                       "Descrivi l'ambiente usando i cinque sensi, enfatizzando il freddo, gli odori sgradevoli.\n"
                       "Sii conciso ma di grande impatto emotivo.\n"
                       "Regola fondamentale: non prendere MAI decisioni per il giocatore.\n"
                       "Termina sempre il tuo turno chiedendo: 'Cosa fai?'"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])

        # 3. Composizione della Catena
        self.chain = self.prompt | self.llm
        
        # 4. Agente con Memoria Persistente
        self.agent_with_memory = RunnableWithMessageHistory(
            self.chain,
            self._get_mongo_history, 
            input_messages_key="input",
            history_messages_key="history"
        )
# per salvare la memoria della chat
    def _get_mongo_history(self, session_id: str):
        """Metodo privato per creare il ponte verso MongoDB."""
        return MongoDBChatMessageHistory(
            connection_string=self.mongo_uri,
            session_id=session_id,
            database_name=DB_NAME,
            collection_name=COLLECTION_NAME,
        )
#oer salvare e gggiornare inventario   
    def get_inventory(self, session_id: str) -> list:
        """
        Controlla se esiste una partita salvata. 
        Se sì, restituisce l'inventario. Se è una partita nuova, crea l'inventario base.
        """
        stato_partita = self.state_db.find_one({"session_id": session_id})
        
        if stato_partita and "inventory" in stato_partita:
            return stato_partita["inventory"]
        else:
            # Setup Iniziale
            inventario_base = ["Fiammiferi", "Chiave arrugginita"]
            self.state_db.update_one(
                {"session_id": session_id},
                {"$set": {"inventory": inventario_base}},
                upsert=True 
            )
            return inventario_base
        
    def esegui_turno(self, input_utente: str, session_id: str = "partita_default"):
        """Questo è l'unico metodo che espongo all'esterno."""
        try:
            risposta = self.agent_with_memory.invoke(
                {"input": input_utente},
                config={"configurable": {"session_id": session_id}}
            )
            return risposta.content
        except Exception as e:
            return f"[Errore dell'Abisso]: Mi sono perso nell'oscurità... ({e})"


# Istanzio l'oggetto engine
engine = AbissoEngine()

INCIPIT = "Ti svegli sul pavimento freddo di una stanza di pietra. Senti l'odore metallico del sangue secco. Non c'è luce. Cosa fai?"

def gioca_turno(messaggio_utente, session_id="partita_ana_01"):
    return engine.esegui_turno(messaggio_utente, session_id)

if __name__ == "__main__":
    print(f"💀 ENGINE AVVIATO - SESSIONE: test_console 💀\n[DM]: {INCIPIT}")
    while True:
        azione = input("\n[Tu]: ")
        if azione.lower() in ["esci", "quit"]: break
        print(f"\n[DM]: {gioca_turno(azione, 'test_console')}")