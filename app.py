import streamlit as st
import uuid  # Importo uuid per generare identificatori unici universali

# Oltre alla funzione per giocare il turno, mi serve l'istanza principale del motore 
# per poter interrogare direttamente il database sullo stato del giocatore.
from src.agent import gioca_turno, INCIPIT, engine 
from src.styles import apply_gothic_style

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Abisso DM", layout="wide")
apply_gothic_style()

# --- 2. GESTIONE DELLO STATO DELLA SESSIONE ---
# Streamlit ricarica l'intera pagina a ogni interazione. 
# Se non salvo l'ID nella "session_state", cambierebbe a ogni invio

# Genero un ID univoco per il giocatore appena entra nel sito, e lo conservo in memoria.
if "session_id" not in st.session_state:
    # Creo un UUID e tengo solo i primi 8 caratteri per comodità visiva
    st.session_state.session_id = f"partita_{str(uuid.uuid4())[:8]}"

# Inizializzo la memoria visiva della chat di Streamlit
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": INCIPIT}]

# --- 3. SIDEBAR ( è Dinamica e connessa al DB) ---
with st.sidebar:
    st.title("📜 Stato dell'Anima")
    st.markdown("---")
    
    # Recupero l'inventario dal database (collezione 'game_state')
    # Uso l'ID univoco di questa sessione per assicurarmi di leggere gli oggetti giusti
    inventario_lista = engine.get_inventory(st.session_state.session_id)
    
    # 2. Formatto i dati per la UI
    # MongoDB mi restituisce una lista Python ["Oggetto A", "Oggetto B"]. 
    inventario_testo = ", ".join(inventario_lista)
    
    # 3. Stampo l'inventario a schermo
    st.info(f"Inventario: {inventario_testo}")
    
    # Stampo l'ID partita per trasparenza architetturale
    st.markdown("---")
    st.caption(f" ID Partita (Database): `{st.session_state.session_id}`")

# --- 4. INTERFACCIA CHAT ---
st.title("☠️ L'Abisso: Dungeon Master")

# Disegno tutti i messaggi sullo schermo
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# --- 5. LOOP DI INTERAZIONE ---
# Quando l'utente preme invio nel box di input:
if prompt := st.chat_input("Scrivi la tua azione..."):
    
    # 1. Aggiungo il messaggio dell'utente alla UI
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # 2. Chiamo il Backend (agent.py) e mostro un caricamento
    with st.chat_message("assistant"):
        with st.spinner("L'Abisso sussurra..."):
            
            # Passo alla logica di business NON SOLO il testo, ma anche l'ID UNIVOCO.
            risposta = gioca_turno(messaggio_utente=prompt, session_id=st.session_state.session_id)
            
            # 3. Mostro la risposta e la salvo nello stato della UI
            st.write(risposta)
            st.session_state.messages.append({"role": "assistant", "content": risposta})