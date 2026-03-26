import os
import re
from dotenv import load_dotenv 
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_mongodb import MongoDBChatMessageHistory
from pymongo import MongoClient
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

DB_NAME = "abisso_db"
COLLECTION_NAME = "chat_history"
STATE_COLLECTION = "game_state" 
MODEL_NAME = "meta-llama/Meta-Llama-3-8B-Instruct"

class AbissoEngine:
    def __init__(self):
        # 1. RECUPERO CREDENZIALI
        self.api_key = os.getenv("H2O_API_KEY")
        self.mongo_uri = os.getenv("MONGO_URI")
        
        if not self.api_key or not self.mongo_uri:
            try:
                import streamlit as st
                self.api_key = st.secrets["H2O_API_KEY"]
                self.mongo_uri = st.secrets["MONGO_URI"]
            except Exception:
                pass

        if not self.api_key: raise ValueError("🚨 ERRORE: Manca H2O_API_KEY!")
        if not self.mongo_uri: raise ValueError("🚨 ERRORE: Manca MONGO_URI!")

        # 2. CONNESSIONE DATABASES
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[DB_NAME]
        self.state_db = self.db[STATE_COLLECTION] 

        # 3. CARICAMENTO CERVELLO RAG (FAISS)
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        self.vector_store = FAISS.load_local("vector_store", self.embeddings, allow_dangerous_deserialization=True)

        # 4. INIZIALIZZO L'IA
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url="https://h2ogpte.genai.h2o.ai/v1",
            model=MODEL_NAME,
            temperature=0.7 
        )

        # 5. PROMPT 
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "Sei un Dungeon Master spietato per un gioco di ruolo horror.\n"
                       "CONTESTO DAL MANUALE (Usa queste informazioni per descrivere l'ambiente): {contesto_rag}\n\n"
                       "ATTENZIONE - INVENTARIO DEL GIOCATORE: {inventario}\n"
                       "Il giocatore possiede SOLO questi oggetti. Non fargli usare cose che non ha.\n\n"
                       "REGOLE DI SISTEMA PER L'INVENTARIO:\n"
                       "Se il giocatore trova, ruba o riceve un nuovo oggetto, devi scrivere alla fine della tua risposta esattamente: [ADD: NomeOggetto]\n"
                       "Se il giocatore perde, usa, o gli viene distrutto un oggetto, scrivi: [REMOVE: NomeOggetto]\n\n"
                       "Descrivi l'ambiente usando i 5 sensi. Termina chiedendo: 'Cosa fai?'"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        
    def _get_mongo_history(self, session_id: str):
        return MongoDBChatMessageHistory(
            connection_string=self.mongo_uri,
            session_id=session_id,
            database_name=DB_NAME,
            collection_name=COLLECTION_NAME,
        )
    
    def get_inventory(self, session_id: str) -> list:
        stato_partita = self.state_db.find_one({"session_id": session_id})
        if stato_partita and "inventory" in stato_partita:
            return stato_partita["inventory"]
        else:
            inventario_base = ["Fiammiferi", "Chiave arrugginita"]
            self.state_db.update_one(
                {"session_id": session_id},
                {"$set": {"inventory": inventario_base}},
                upsert=True 
            )
            return inventario_base

    def _modifica_inventario_db(self, session_id: str, azione: str, oggetto: str):
        if azione == "ADD":
            self.state_db.update_one({"session_id": session_id}, {"$push": {"inventory": oggetto}})
        elif azione == "REMOVE":
            self.state_db.update_one({"session_id": session_id}, {"$pull": {"inventory": oggetto}})

    def esegui_turno(self, input_utente: str, session_id: str):
        try:
            inventario_lista = self.get_inventory(session_id)
            inventario_str = ", ".join(inventario_lista) if inventario_lista else "Vuoto (non hai nulla)"

            frammenti_trovati = self.vector_store.similarity_search(input_utente, k=2) 
            contesto_str = "\n".join([doc.page_content for doc in frammenti_trovati])

            storico_db = self._get_mongo_history(session_id)
            
            # --- 1. SANITIZZAZIONE ESTREMA DEL DATABASE ---
            # Ripuliamo qualsiasi schifezza o stringa salvata su MongoDB in passato
            messaggi_precedenti = []
            for msg in storico_db.messages:
                if hasattr(msg, "content"):
                    messaggi_precedenti.append(msg)
                elif isinstance(msg, dict) and "content" in msg:
                    messaggi_precedenti.append(HumanMessage(content=msg["content"]))
                elif isinstance(msg, str):
                    messaggi_precedenti.append(HumanMessage(content=msg))

            # --- 2. COSTRUZIONE MANUALE DEL PROMPT ---
            messaggi_compilati = self.prompt.format_messages(
                input=input_utente, 
                inventario=inventario_str, 
                contesto_rag=contesto_str,  # <--- CORRETTO!
                history=messaggi_precedenti
            )

            # --- 3. DOPPIA VERIFICA ---
            messaggi_puliti = []
            for m in messaggi_compilati:
                if isinstance(m, str):
                    messaggi_puliti.append(HumanMessage(content=m))
                else:
                    messaggi_puliti.append(m)

            # --- 4. CHIAMATA DIRETTA E PURA AL MODELLO ---
            # Senza l'uso di "chain" opache
            risposta = self.llm.invoke(messaggi_puliti)
            testo_ia = risposta.content

            messaggio_umano = HumanMessage(content=input_utente)
            messaggio_ia = AIMessage(content=testo_ia)
            
            storico_db.add_message(messaggio_umano)
            storico_db.add_message(messaggio_ia)

            aggiunte = re.findall(r'\[ADD:\s*(.*?)\]', testo_ia)
            rimozioni = re.findall(r'\[REMOVE:\s*(.*?)\]', testo_ia)

            for oggetto in aggiunte: self._modifica_inventario_db(session_id, "ADD", oggetto)
            for oggetto in rimozioni: self._modifica_inventario_db(session_id, "REMOVE", oggetto)

            testo_pulito = re.sub(r'\[ADD:\s*.*?\]', '', testo_ia)
            testo_pulito = re.sub(r'\[REMOVE:\s*.*?\]', '', testo_pulito)

            return testo_pulito.strip()

        except Exception as e:
            return f"[Errore di Sistema - L'Abisso è corrotto]: {e}"

engine = AbissoEngine()
INCIPIT = "Ti svegli sul pavimento freddo di una stanza di pietra. Senti l'odore metallico del sangue secco. Non c'è luce. Cosa fai?"

def gioca_turno(messaggio_utente, session_id):
    return engine.esegui_turno(messaggio_utente, session_id)