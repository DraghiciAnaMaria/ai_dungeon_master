import os
import re
import traceback
from dotenv import load_dotenv 
from openai import OpenAI  
from pymongo import MongoClient

# Componenti LangChain (usati solo per quello che sanno fare bene: Data & RAG)
from langchain_core.messages import HumanMessage, AIMessage
from langchain_mongodb import MongoDBChatMessageHistory
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

# --- CONFIGURAZIONE COSTANTI (Scalabilità) ---
DB_NAME = "abisso_db"
COLLECTION_NAME = "chat_history"
STATE_COLLECTION = "game_state" 

# Passiamo a Groq (Llama 3 8B) per stabilità e velocità
MODEL_NAME = "llama3-8b-8192" 
BASE_URL = "https://api.groq.com/openai/v1"

class AbissoEngine:
    """
    Engine modulare per il Dungeon Master.
    Architettura: RAG (FAISS) + NoSQL (MongoDB) + LLM (Provider agnostico via OpenAI Client).
    """
    def __init__(self):
        # 1. SETUP CREDENZIALI (Fallback tra env e streamlit secrets)
        self.api_key = os.getenv("GROQ_API_KEY") or self._get_st_secret("GROQ_API_KEY")
        self.mongo_uri = os.getenv("MONGO_URI") or self._get_st_secret("MONGO_URI")
        
        if not self.api_key or not self.mongo_uri:
            raise ValueError("🚨 MANCANO LE CHIAVI! Controlla .env o Streamlit Secrets.")

        # 2. DATA LAYER (MongoDB)
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[DB_NAME]
        self.state_db = self.db[STATE_COLLECTION] 

        # 3. KNOWLEDGE LAYER (RAG con FAISS)
        # Usiamo embeddings locali per non pagare chiamate API extra
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        try:
            self.vector_store = FAISS.load_local("vector_store", self.embeddings, allow_dangerous_deserialization=True)
        except Exception as e:
            print(f"⚠️ Errore caricamento Vector Store: {e}. Il RAG sarà disabilitato.")
            self.vector_store = None

        # 4. INFERENCE LAYER (Client Nativo OpenAI)
        # Disaccoppiato da LangChain per evitare errori di serializzazione (es. .model_dump())
        self.ia_client = OpenAI(api_key=self.api_key, base_url=BASE_URL)
        
    def _get_st_secret(self, key):
        """Helper per recuperare segreti da Streamlit in produzione."""
        try:
            import streamlit as st
            return st.secrets[key]
        except: return None

    def _get_mongo_history(self, session_id: str):
        """Recupera lo storico messaggi formattato per LangChain/MongoDB."""
        return MongoDBChatMessageHistory(
            connection_string=self.mongo_uri,
            session_id=session_id,
            database_name=DB_NAME,
            collection_name=COLLECTION_NAME,
        )
    
    def get_inventory(self, session_id: str) -> list:
        """Recupera l'inventario dal DB o inizializza il set base per nuovi player."""
        doc = self.state_db.find_one({"session_id": session_id})
        if doc and "inventory" in doc:
            return doc["inventory"]
        
        initial_inv = ["Fiammiferi", "Chiave arrugginita"]
        self.state_db.update_one({"session_id": session_id}, {"$set": {"inventory": initial_inv}}, upsert=True)
        return initial_inv

    def _update_inventory_logic(self, session_id: str, text: str):
        """Parsing della risposta IA per aggiornare il DB (Regex pattern: [ADD: x] o [REMOVE: x])."""
        adds = re.findall(r'\[ADD:\s*(.*?)\]', text)
        removes = re.findall(r'\[REMOVE:\s*(.*?)\]', text)

        for item in adds:
            self.state_db.update_one({"session_id": session_id}, {"$push": {"inventory": item}})
        for item in removes:
            self.state_db.update_one({"session_id": session_id}, {"$pull": {"inventory": item}})

    def esegui_turno(self, input_utente: str, session_id: str):
        """Main Loop del turno: RAG -> Prompt -> LLM -> DB -> UI."""
        try:
            # --- PHASE 1: CONTEXT RETRIEVAL ---
            inv_list = self.get_inventory(session_id)
            inv_str = ", ".join(inv_list) if inv_list else "Vuoto"
            
            rag_context = ""
            if self.vector_store:
                docs = self.vector_store.similarity_search(input_utente, k=2)
                rag_context = "\n".join([d.page_content for d in docs])

            # --- PHASE 2: PROMPT ENGINEERING (Manual Construction) ---
            messages = [
                {"role": "system", "content": (
                    "Sei un Dungeon Master horror spietato.\n"
                    f"INFO MANUALE: {rag_context}\n"
                    f"INVENTARIO ATTUALE: {inv_str}\n"
                    "Usa i tag [ADD: Oggetto] o [REMOVE: Oggetto] per gestire l'inventario."
                )}
            ]

            # Iniezione dello storico (Sanitizzazione dei tipi)
            history_manager = self._get_mongo_history(session_id)
            for m in history_manager.messages:
                role = "assistant" if isinstance(m, AIMessage) else "user"
                messages.append({"role": role, "content": str(m.content)})

            messages.append({"role": "user", "content": input_utente})

            # --- PHASE 3: ROBUST INFERENCE ---
            response = self.ia_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.7
            )

            # Duck Typing per gestire risposte sporche/HTML/stringhe grezze dai server
            if hasattr(response, 'choices'):
                ai_text = response.choices[0].message.content
            elif isinstance(response, dict):
                ai_text = response['choices'][0]['message']['content']
            else:
                ai_text = str(response)

            # --- PHASE 4: STATE PERSISTENCE ---
            history_manager.add_message(HumanMessage(content=input_utente))
            history_manager.add_message(AIMessage(content=ai_text))
            self._update_inventory_logic(session_id, ai_text)

            # Pulizia dei tag tecnici prima di mostrare all'utente
            clean_output = re.sub(r'\[(ADD|REMOVE):\s*.*?\]', '', ai_text).strip()
            return clean_output

        except Exception as e:
            return f"🚨 [SYSTEM_CRASH]: {str(e)}\n{traceback.format_exc()}"

# Singleton instance per l'app
engine = AbissoEngine()
INCIPIT = "Ti svegli nell'oscurità totale. L'Abisso ti osserva. Cosa fai?"

def gioca_turno(messaggio_utente, session_id): # <-- Cambia i nomi qui
    return engine.esegui_turno(messaggio_utente, session_id)