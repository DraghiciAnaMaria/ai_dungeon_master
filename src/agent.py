import os
import re
import traceback
import random
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

    def get_game_state(self, session_id: str):
        doc = self.state_db.find_one({"session_id": session_id})
        if not doc:
            doc = {
                "session_id": session_id,
                "inventory": ["Fiammiferi", "Chiave arrugginita"],
                "sanita": 100,
                "party": [] 
            }
            self.state_db.insert_one(doc)
        return doc

    def update_stat(self, session_id: str, field: str, value, op="$set"):
        self.state_db.update_one({"session_id": session_id}, {op: {field: value}})

    def risolvi_lancio_dado(self, session_id, risultato):
        if risultato <= 5:
            self.update_stat(session_id, "sanita", -15, op="$inc")
            return "FALLIMENTO DISASTROSO! L'Abisso ti ha segnato negativamente."
        elif risultato >= 15:
            return "SUCCESSO ECCEZIONALE! Uno spiraglio di luce ti ha salvato."
        else:
            return "ESITO INCERTO: Sopravvivi, ma a caro prezzo."

    def genera_riassunto(self, session_id):
        """Genera una sintesi profonda dell'avventura."""
        history_manager = MongoDBChatMessageHistory(
            connection_string=self.mongo_uri, session_id=session_id,
            database_name=DB_NAME, collection_name=COLLECTION_NAME
        )
        messaggi = history_manager.messages
        if not messaggi: return "L'oscurità non ha ancora una storia."
        
        testo_storico = "\n".join([f"{m.type}: {m.content[:200]}" for m in messaggi[-15:]])
        prompt = f"Riassumi questa cronaca dell'Abisso in 3 frasi epiche e oscure:\n{testo_storico}"
        
        res = self.ia_client.chat.completions.create(
            model=MODEL_NAME, 
            messages=[{"role": "system", "content": "Sei un bardo oscuro."}, {"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content

    def esegui_turno(self, input_utente: str, session_id: str):
        try:
            stato = self.get_game_state(session_id)
            inv_str = ", ".join(stato["inventory"])
            party_list = stato["party"]
            party_str = ", ".join(party_list) if party_list else "Nessuno (Sei solo)"
            sanita = stato["sanita"]
            
            rag_context = ""
            if self.vector_store:
                docs = self.vector_store.similarity_search(input_utente, k=3)
                rag_context = "\n".join([d.page_content for d in docs])

            # --- PROMPT OTTIMIZZATO ---
            testo_sistema = (
                "Sei il Dungeon Master dell'Abisso. La tua narrazione è horror, viscerale e psicologica.\n"
                f"LORE DI RIFERIMENTO:\n{rag_context}\n\n"
                f"STATO ATTUALE:\n- Party: {party_str}\n- Inventario: {inv_str}\n- Sanità: {sanita}%\n\n"
                "REGOLE COMPORTAMENTALI RIGIDE:\n"
                "1. GESTIONE PARTY: Se un personaggio NON è nel 'Party', il giocatore non lo conosce. Se lo incontra ora, usa [MEET: Nome]. "
                "Solo DOPO l'incontro il personaggio può parlare o aiutare. Non far apparire Joe o Emilia dal nulla se non sono nel party.\n"
                "2. MECCANICA DADI: Usa [DICE_ROLL] SOLO per azioni critiche (combattimento, fuga, prove fisiche). NON usarlo per dialoghi o esplorazione semplice.\n"
                "3. INVENTARIO: Usa [ADD: Oggetto] o [REMOVE: Oggetto] solo per oggetti materiali piccoli. Niente persone o concetti astratti.\n"
                "4. PERSONAGGI: Joe è impulsivo e protettivo. Emilia è criptica e ossessionata dai geroglifici. Falli interagire tra loro solo se entrambi sono nel party.\n"
                "5. ATMOSFERA: Non essere mai rassicurante. L'Abisso è vivo e ostile."
            )

            messages = [{"role": "system", "content": testo_sistema}]
            history_manager = MongoDBChatMessageHistory(
                connection_string=self.mongo_uri, session_id=session_id,
                database_name=DB_NAME, collection_name=COLLECTION_NAME
            )
            # Carica storico limitato per mantenere focus
            for m in history_manager.messages[-10:]:
                role = "assistant" if isinstance(m, AIMessage) else "user"
                messages.append({"role": role, "content": str(m.content)})
            messages.append({"role": "user", "content": input_utente})

            response = self.ia_client.chat.completions.create(model=MODEL_NAME, messages=messages, temperature=0.7)
            ai_text = response.choices[0].message.content

            # --- PARSING AVANZATO ---
            # Filtro Inventario Anti-Errore
            blacklist = ["persona", "misteriosa", "uomo", "donna", "ombra", "joe", "emilia"]
            adds = re.findall(r'\[ADD:\s*(.*?)\]', ai_text)
            for item in adds:
                if len(item) < 30 and not any(word in item.lower() for word in blacklist):
                    self.update_stat(session_id, "inventory", item.strip(), op="$push")

            rems = re.findall(r'\[REMOVE:\s*(.*?)\]', ai_text)
            for item in rems: self.update_stat(session_id, "inventory", item.strip(), op="$pull")

            # Incontri
            nuovi_amici = re.findall(r'\[MEET:\s*(.*?)\]', ai_text)
            for amico in nuovi_amici:
                nome_pulito = amico.strip()
                if nome_pulito not in party_list:
                    self.update_stat(session_id, "party", nome_pulito, op="$push")
            
            # Sanità
            perdite = re.findall(r'\[SANITY_LOSS:\s*(\d+)\]', ai_text)
            for p in perdite: self.update_stat(session_id, "sanita", -int(p), op="$inc")

            history_manager.add_message(HumanMessage(content=input_utente))
            history_manager.add_message(AIMessage(content=ai_text))
            
            clean_output = re.sub(r'\[.*?\]', '', ai_text).strip()
            needs_dice = "[DICE_ROLL]" in ai_text
            
            return {"testo": clean_output, "dice": needs_dice}

        except Exception as e:
            return {"testo": f"🚨 [ERRORE ENGINE]: {str(e)}", "dice": False}

engine = AbissoEngine()
INCIPIT = "Ti svegli nell'oscurità totale. Il silenzio è interrotto solo dal tuo respiro affannoso. L'Abisso ti osserva. Cosa fai?"

def gioca_turno(msg, sid):
    return engine.esegui_turno(msg, sid)