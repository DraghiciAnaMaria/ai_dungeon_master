import os
import re
import traceback
import random # <--- Nuovo per i dadi
from dotenv import load_dotenv 
from openai import OpenAI  
from pymongo import MongoClient
from langchain_core.messages import HumanMessage, AIMessage
from langchain_mongodb import MongoDBChatMessageHistory
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

DB_NAME = "abisso_db"
COLLECTION_NAME = "chat_history"
STATE_COLLECTION = "game_state" 
MODEL_NAME = "llama-3.3-70b-versatile" 
BASE_URL = "https://api.groq.com/openai/v1"

class AbissoEngine:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY") or self._get_st_secret("GROQ_API_KEY")
        self.mongo_uri = os.getenv("MONGO_URI") or self._get_st_secret("MONGO_URI")
        
        if not self.api_key or not self.mongo_uri:
            raise ValueError("🚨 MANCANO LE CHIAVI!")

        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[DB_NAME]
        self.state_db = self.db[STATE_COLLECTION] 

        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        try:
            self.vector_store = FAISS.load_local("vector_store", self.embeddings, allow_dangerous_deserialization=True)
        except:
            self.vector_store = None

        self.ia_client = OpenAI(api_key=self.api_key, base_url=BASE_URL)
        
    def _get_st_secret(self, key):
        try:
            import streamlit as st
            return st.secrets[key]
        except: return None

    # --- NUOVO: GESTIONE STATO AVANZATO ---
    def get_game_state(self, session_id: str):
        """Recupera sanità, inventario e party dal DB."""
        doc = self.state_db.find_one({"session_id": session_id})
        if not doc:
            doc = {
                "session_id": session_id,
                "inventory": ["Fiammiferi", "Chiave arrugginita"],
                "sanita": 100,
                "party": [] # Personaggi incontrati
            }
            self.state_db.insert_one(doc)
        return doc

    def update_stat(self, session_id: str, field: str, value, op="$set"):
        """Aggiorna genericamente un campo dello stato nel DB."""
        self.state_db.update_one({"session_id": session_id}, {op: {field: value}})
    
    def risolvi_lancio_dado(self, session_id, risultato):
        if risultato <= 5:
            self.update_stat(session_id, "sanita", -15, op="$inc")
            return "FALLIMENTO DISASTROSO! L'Abisso ti ha segnato."
        elif risultato >= 15:
            return "SUCCESSO ECCEZIONALE! Uno spiraglio di luce ti salva."
        else:
            return "ESITO INCERTO: Ti salvi, ma il prezzo è l'incertezza."
    
    def esegui_turno(self, input_utente: str, session_id: str):
        try:
            # 1. Recupero stato
            stato = self.get_game_state(session_id)
            inv_str = ", ".join(stato["inventory"])
            party_str = ", ".join(stato["party"]) if stato["party"] else "Sei solo"
            sanita = stato["sanita"]
            
            rag_context = ""
            if self.vector_store:
                docs = self.vector_store.similarity_search(input_utente, k=2)
                rag_context = "\n".join([d.page_content for d in docs])

            # 2. Prompt con Dinamiche di Gruppo e Dadi
            testo_sistema = (
                "Sei un Dungeon Master horror spietato. Usa i manuali per i dettagli.\n"
                f"MANUALE: {rag_context}\n"
                f"SITUAZIONE PARTY: Inventario:[{inv_str}] | Sanità:[{sanita}%] | Compagni:[{party_str}]\n\n"
                "REGOLE DINAMICHE:\n"
                "- Se il giocatore incontra Emilia o Joe, scrivi alla fine: [MEET: Nome]\n"
                "- Se l'azione è rischiosa o incerta, scrivi alla fine: [DICE_ROLL]\n"
                "- Se il giocatore subisce uno shock, scrivi: [SANITY_LOSS: 10]\n"
                "- Fai parlare Emilia (misteriosa/geroglifici) e Joe (soldato/impulsivo) se sono nel party.\n"
                "- Usa i tag [ADD: oggetto] o [REMOVE: oggetto].\n"
                "Descrivi in modo immersivo. Termina sempre con una domanda."
            )

            messages = [{"role": "system", "content": testo_sistema}]
            history_manager = MongoDBChatMessageHistory(
                connection_string=self.mongo_uri, session_id=session_id,
                database_name=DB_NAME, collection_name=COLLECTION_NAME
            )
            for m in history_manager.messages:
                role = "assistant" if isinstance(m, AIMessage) else "user"
                messages.append({"role": role, "content": str(m.content)})
            messages.append({"role": "user", "content": input_utente})

            # 3. Chiamata API
            response = self.ia_client.chat.completions.create(model=MODEL_NAME, messages=messages, temperature=0.8)
            ai_text = response.choices[0].message.content

            # 4. Parsing Logica (Incontri, Sanità, Inventario)
            # Incontri
            nuovi_amici = re.findall(r'\[MEET:\s*(.*?)\]', ai_text)
            for amico in nuovi_amici:
                if amico not in stato["party"]:
                    self.update_stat(session_id, "party", amico, op="$push")
            
            # Sanità
            perdite = re.findall(r'\[SANITY_LOSS:\s*(\d+)\]', ai_text)
            for p in perdite:
                self.update_stat(session_id, "sanita", -int(p), op="$inc")

            # Inventario
            adds = re.findall(r'\[ADD:\s*(.*?)\]', ai_text)
            rems = re.findall(r'\[REMOVE:\s*(.*?)\]', ai_text)
            for item in adds: self.update_stat(session_id, "inventory", item, op="$push")
            for item in rems: self.update_stat(session_id, "inventory", item, op="$pull")

            # 5. Salvataggio e Pulizia
            history_manager.add_message(HumanMessage(content=input_utente))
            history_manager.add_message(AIMessage(content=ai_text))
            
            # Puliamo TUTTI i tag tecnici prima di restituire il testo
            clean_output = re.sub(r'\[.*?\]', '', ai_text).strip()
            
            # Passiamo il flag del dado all'interfaccia
            needs_dice = "[DICE_ROLL]" in ai_text
            
            return {"testo": clean_output, "dice": needs_dice}

        except Exception as e:
            return {"testo": f"🚨 [CRASH]: {str(e)}", "dice": False}

engine = AbissoEngine()
INCIPIT = "Ti svegli nell'oscurità totale. L'Abisso ti osserva. Cosa fai?"

def gioca_turno(msg, sid):
    return engine.esegui_turno(msg, sid)