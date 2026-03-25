import os
from dotenv import load_dotenv 
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_mongodb import MongoDBChatMessageHistory

# Carico le variabili d'ambiente. È la prima cosa che faccio perché senza chiavi l'app è morta.
load_dotenv()

# --- CONFIGURAZIONE GLOBALE (Clean Code) ---
# Ho spostato queste stringhe fuori dalle classi. Se devo cambiare il nome del DB 
# durante il deploy, lo faccio qui in un secondo.
DB_NAME = "abisso_db"
COLLECTION_NAME = "chat_history"
MODEL_NAME = "llama-3.3-70b-versatile"

class AbissoEngine:
    """
    In questa classe ho racchiuso il 'Cervello' del Dungeon Master. 
    L'ho strutturata così per isolare le responsabilità: la classe sa come parlare con l'IA 
    e con il DB, ma non le interessa come verranno visualizzati i dati su Streamlit.
    """
    
    def __init__(self):
        # Recupero le credenziali. Uso os.getenv perché è più sicuro che scriverle in chiaro.
        self.api_key = os.getenv("GROQ_API_KEY")
        self.mongo_uri = os.getenv("MONGO_URI")
        
        # Validation check
        if not self.api_key or not self.mongo_uri:
            raise ValueError("Mancano le configurazioni ambientali (API Key o Mongo URI)!")

        # 1. Configurazione del Modello (LLM)
        # Sto usando Llama 3 tramite Groq per avere prestazioni da top di gamma a costo zero.
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
            model=MODEL_NAME,
            temperature=0.7 # Un po' di creatività per l'horror.
        )

        # 2. Il Prompt Template
        # Uso 'system' per il comportamento, 'history' per la memoria e 'human' per l'input.
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "Sei un Dungeon Master spietato e inquietante per un gioco di ruolo horror psicologico.\n"
                       "Descrivi l'ambiente usando i cinque sensi, enfatizzando il freddo, gli odori sgradevoli.\n"
                       "Sii conciso ma di grande impatto emotivo.\n"
                       "Regola fondamentale: non prendere MAI decisioni per il giocatore.\n"
                       "Termina sempre il tuo turno chiedendo: 'Cosa fai?'"),
            # Questo segnaposto è dove LangChain inietterà i messaggi recuperati da MongoDB.
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])

        # 3. Composizione della Catena (LCEL - LangChain Expression Language)
        # Uso l'operatore pipe | per 'incatenare' i componenti.
        self.chain = self.prompt | self.llm
        
        # 4. Agente con Memoria Persistente
        # RunnableWithMessageHistory avvolge la mia catena e gestisce il DB automaticamente.
        self.agent_with_memory = RunnableWithMessageHistory(
            self.chain,
            self._get_mongo_history, # Passo il metodo per connettersi al DB come callback
            input_messages_key="input",
            history_messages_key="history"
        )

    def _get_mongo_history(self, session_id: str):
        """
        Metodo privato (inizia con _ per convenzione). 
        Si occupa solo di creare il ponte verso MongoDB Atlas usando il session_id dell'utente.
        """
        return MongoDBChatMessageHistory(
            connection_string=self.mongo_uri,
            session_id=session_id,
            database_name=DB_NAME,
            collection_name=COLLECTION_NAME,
        )

    def esegui_turno(self, input_utente: str, session_id: str = "partita_default"):
        """
        Questo è l'unico metodo che espongo all'esterno.
        Prende l'azione dell'utente e restituisce la risposta del DM, 
        gestendo la persistenza in background.
        """
        try:
            # Invoco l'agente passando la configurazione della sessione.
            risposta = self.agent_with_memory.invoke(
                {"input": input_utente},
                config={"configurable": {"session_id": session_id}}
            )
            return risposta.content
        except Exception as e:
            # Gestisco l'eccezione per evitare che l'intera UI si rompa.
            return f"[Errore dell'Abisso]: Mi sono perso nell'oscurità... ({e})"

# --- PATTERN SINGLETON ---
# Istanzio l'oggetto engine qui. In questo modo, quando app.py lo importa, 
# non deve ricreare tutto da capo ogni volta, risparmiando risorse.
engine = AbissoEngine()

# Testo statico dell'incipit 
INCIPIT = "Ti svegli sul pavimento freddo di una stanza di pietra. Senti l'odore metallico del sangue secco. Non c'è luce. Cosa fai?"

# Funzione wrapper per retrocompatibilità (facilita la transizione del vecchio codice)
def gioca_turno(messaggio_utente, session_id="partita_ana_01"):
    return engine.esegui_turno(messaggio_utente, session_id)

# --- TEST SU CONSOLE ---
if __name__ == "__main__":
    # Questo blocco gira solo se lancio il file direttamente. Utile per il debug veloce.
    print(f"💀 ENGINE AVVIATO - SESSIONE: test_console 💀\n[DM]: {INCIPIT}")
    while True:
        azione = input("\n[Tu]: ")
        if azione.lower() in ["esci", "quit"]: break
        print(f"\n[DM]: {gioca_turno(azione, 'test_console')}")