import streamlit as st
import uuid
from src.agent import gioca_turno, INCIPIT, engine 
from src.styles import apply_gothic_style

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Abisso DM", layout="wide")
apply_gothic_style()

# --- FUNZIONI DI SUPPORTO (State Management) ---
def avvia_nuova_partita():
    """Genera un nuovo ID e pulisce la chat per iniziare da zero."""
    st.session_state.session_id = f"partita_{str(uuid.uuid4())[:8]}"
    st.session_state.messages = [{"role": "assistant", "content": INCIPIT}]

def carica_partita(id_inserito):
    """Carica l'ID e va a pescare la vecchia conversazione da MongoDB."""
    if id_inserito:
        st.session_state.session_id = id_inserito
        
        # Pesco la cronologia dal database tramite LangChain
        storico_db = engine._get_mongo_history(id_inserito).messages
        
        st.session_state.messages = []
        if not storico_db:
            # Se l'ID non esiste, creo una stanza vuota col messaggio di base
            st.session_state.messages = [{"role": "assistant", "content": INCIPIT}]
        else:
            # Se esiste, converto i messaggi del DB nel formato visivo di Streamlit
            for msg in storico_db:
                ruolo = "user" if msg.type == "human" else "assistant"
                st.session_state.messages.append({"role": ruolo, "content": msg.content})

def esci_partita():
    """Distrugge le variabili di sessione per 'sloggarsi'."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]

# --- 2. SIDEBAR (Il nuovo Menu di Gioco) ---
with st.sidebar:
    st.title("☠️ Il Portale dell'Abisso")
    st.markdown("---")
    
    # CASO A: Il giocatore NON è in partita (Menu di Login)
    if "session_id" not in st.session_state:
        st.subheader("Inizia l'Avventura")
        if st.button("🩸 Nuova Partita", use_container_width=True):
            avvia_nuova_partita()
            st.rerun() # Forza il riavvio della pagina per applicare le modifiche
        
        st.markdown("---")
        st.subheader("Carica Partita")
        id_input = st.text_input("Inserisci il tuo ID Partita:", placeholder="es. partita_1234abcd")
        if st.button("Carica", use_container_width=True):
            carica_partita(id_input)
            st.rerun()
            
    # CASO B: Il giocatore È in partita (Menu di Gioco)
    else:
        st.success("Connesso all'Abisso")
        st.caption(f"ID Salvataggio: `{st.session_state.session_id}`\n\n*(Salva questo codice per riprendere a giocare!)*")
        st.markdown("---")
        
        # Mostro l'inventario aggiornato
        inventario_lista = engine.get_inventory(st.session_state.session_id)
        inventario_testo = ", ".join(inventario_lista) if inventario_lista else "Vuoto (non hai nulla)"
        st.info(f"🎒 Inventario:\n{inventario_testo}")
        
        st.markdown("---")
        # Il tasto per uscire e tornare al menu principale
        if st.button("🚪 Esci dalla Partita", type="primary", use_container_width=True):
            esci_partita()
            st.rerun()

# --- 3. INTERFACCIA CHAT PRINCIPALE ---
# Se c'è una sessione attiva, mostro il gioco
if "session_id" in st.session_state:
    st.title("☠️ L'Abisso: Dungeon Master")

    # Disegno i messaggi (che ora includono quelli caricati dal DB!)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Box di input
    if prompt := st.chat_input("Scrivi la tua azione..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("L'Abisso sussurra..."):
                risposta = gioca_turno(messaggio_utente=prompt, session_id=st.session_state.session_id)
                st.write(risposta)
                st.session_state.messages.append({"role": "assistant", "content": risposta})
# Se non c'è sessione attiva, mostro una schermata di attesa
else:
    st.markdown("<h2 style='text-align: center; color: gray; margin-top: 20%;'>Usa il menu laterale per varcare la soglia.</h2>", unsafe_allow_html=True)