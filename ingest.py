import os
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

print("python ingest.py Inizio il rituale di assimilazione dei tomi...")

# 1. LETTURA (Document Loader)
# Dico a LangChain di andare nella cartella 'docs' e leggere TUTTI i PDF che trova.
# Se in futuro aggiungerò "storia.pdf" o "mostri.pdf", li leggerà in automatico.
print("1. Leggo i documenti PDF dalla cartella 'docs/...")
loader = PyPDFDirectoryLoader("docs")
documenti_grezzi = loader.load()
print(f"   Trovate {len(documenti_grezzi)} pagine.")

# 2. SPEZZETTAMENTO (Chunking)
# L'IA non può leggere un libro intero in un secondo. Taglio il testo in "fette" da 1000 caratteri.
# chunk_overlap=200 significa che ogni fetta condivide 200 caratteri con la precedente, 
# così non si perde il contesto se una frase viene tagliata a metà.
print("2. Taglio i testi in frammenti assimilabili (Chunking)...")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
frammenti = text_splitter.split_documents(documenti_grezzi)
print(f"   Testo diviso in {len(frammenti)} frammenti concettuali.")

# 3. TRADUZIONE IN NUMERI (Embeddings)
# Uso un modello Open Source gratuito di HuggingFace per trasformare le parole in vettori matematici.
print("3. Traduco i frammenti in coordinate vettoriali (Embeddings)...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# 4. SALVATAGGIO NEL DATABASE VETTORIALE (Vector Store)
# Prendo i frammenti e i vettori e li salvo dentro FAISS (il database super-veloce di Meta).
print("4. Creo il database vettoriale FAISS...")
vector_store = FAISS.from_documents(frammenti, embeddings)

# Salvo fisicamente il database in una nuova cartella chiamata "vector_store"
cartella_salvataggio = "vector_store"
vector_store.save_local(cartella_salvataggio)

print(f"✅ Rituale completato! La memoria a lungo termine è salvata in '{cartella_salvataggio}'.")