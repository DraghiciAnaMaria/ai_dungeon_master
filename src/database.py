import os
from langchain_mongodb import MongoDBChatMessageHistory

def get_mongo_history(session_id: str):
    """Configura la persistenza dei messaggi su MongoDB Atlas"""
    uri = os.getenv("MONGO_URI")
    if not uri:
        raise ValueError("ERRORE: MONGO_URI non trovata!")
    
    return MongoDBChatMessageHistory(
        connection_string=uri,
        session_id=session_id,
        database_name="abisso_db",
        collection_name="chat_history",
    )