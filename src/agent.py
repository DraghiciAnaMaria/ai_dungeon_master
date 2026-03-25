import os  # Gestione variabili d'ambiente
from dotenv import load_dotenv  # Sicurezza credenziali
# Passo dall'SDK base di OpenAI alle classi di LangChain per poter orchestrare la memoria
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

# isolo le chiavi nel file .env per non esporle
load_dotenv()
api_key = os.getenv("GROQ_API_KEY") 
if not api_key:
    raise ValueError("ERRORE CRITICO: Chiave GROQ_API_KEY non trovata nel file .env!")

# Avvolgo il client in ChatOpenAI di LangChain, ma continuo a reindirizzare su GroqCloud  per usare LLaMA 3 a costo zero.
llm = ChatOpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1",
    model="llama-3.3-70b-versatile",
    temperature=0.7
)

# PROMPT ENGINEERING DINAMICO
prompt = ChatPromptTemplate.from_messages([
    # Il System Prompt stabilisce il comportamento base dell'agente
    ("system", "Sei un Dungeon Master spietato e inquietante per un gioco di ruolo horror psicologico.\n"
               "Descrivi l'ambiente usando i cinque sensi, enfatizzando il freddo, gli odori sgradevoli.\n"
               "Sii conciso ma di grande impatto emotivo.\n"
               "Regola fondamentale: non prendere MAI decisioni per il giocatore.\n"
               "Termina sempre il tuo turno chiedendo: 'Cosa fai?'"),
    # Il segnaposto: qui LangChain inietterà in automatico tutta la cronologia passata della chat
    MessagesPlaceholder(variable_name="history"), 
    # L'input corrente che digito da tastiera in questo turno
    ("human", "{input}")
])

# Utilizzo la sintassi moderna LCEL (LangChain Expression Language). 
# Il simbolo della pipe "|" incatena gli oggetti: passa l'output del prompt direttamente all'LLM.
chain = prompt | llm

# 4. GESTIONE DELLA MEMORIA (Session State)
# Creo un dizionario che funge da database temporaneo per salvare le sessioni di gioco.
store = {}

def get_session_history(session_id: str):
    # Se la partita non esiste nel dizionario, creo una nuova cronologia vuota
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

# Assemblo l'Agente definitivo: unisco la catena logica al sistema di recupero/salvataggio cronologia
agent_with_memory = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history" # Deve coincidere col nome del MessagesPlaceholder
)

# Definiamo l'inizio della storia una volta sola qui
INCIPIT = "Ti svegli sul pavimento freddo di una stanza di pietra. Senti l'odore metallico del sangue secco. Non c'è luce. Cosa fai?"

def gioca_turno(messaggio_utente):
    try:
        risposta = agent_with_memory.invoke(
            {"input": messaggio_utente},
            config={"configurable": {"session_id": "partita_01"}}
        )
        return risposta.content 
    except Exception as e:
        return f"[Errore di Sistema: {e}]"

# 5. LOOP DI GIOCO (Core Logic per Terminale)
if __name__ == "__main__":
    print("="*60)
    print(" 💀 BENVENUTO NELL'ABISSO - AI DUNGEON MASTER 💀 ")
    print("="*60)
    
    # Usiamo la variabile INCIPIT invece del testo fisso
    print(f"\n[DM]: {INCIPIT}")
    
    while True:
        azione = input("\n[Tu]: ") 
        if azione.lower() in ["esci", "quit", "stop"]:
            break
        print(f"\n[DM]: {gioca_turno(azione)}")