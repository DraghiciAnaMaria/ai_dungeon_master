import streamlit as st
from src.agent import gioca_turno, INCIPIT  # <--- Importiamo anche INCIPIT
from src.styles import apply_gothic_style

# 1. Configurazione
st.set_page_config(page_title="Abisso DM", layout="wide")
apply_gothic_style()

# 2. Sidebar
with st.sidebar:
    st.title(" Stato dell'Anima")
    st.markdown("---")
    st.info("Inventario: Fiammiferi, Chiave arrugginita")

# 3. Interfaccia Chat
st.title("☠️ L'Abisso: Dungeon Master")

# Inizializziamo la chat usando la variabile importata dal backend
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": INCIPIT}] # <--- Usiamo INCIPIT

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if prompt := st.chat_input("Scrivi la tua azione..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("L'Abisso sussurra..."):
            risposta = gioca_turno(prompt)
            st.write(risposta)
            st.session_state.messages.append({"role": "assistant", "content": risposta})