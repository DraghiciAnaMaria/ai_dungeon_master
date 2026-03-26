import streamlit as st
import uuid
import random
from src.agent import gioca_turno, INCIPIT, engine 
from src.styles import apply_gothic_style

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Abisso DM", layout="wide")
apply_gothic_style()

# --- FUNZIONI DI SUPPORTO ---
def avvia_nuova_partita():
    st.session_state.session_id = f"partita_{str(uuid.uuid4())[:8]}"
    # Inizializziamo lo stato anche nel DB al primo avvio
    engine.get_game_state(st.session_state.session_id)
    st.session_state.messages = [{"role": "assistant", "content": INCIPIT}]
    st.session_state.attesa_dadi = False

def carica_partita(id_inserito):
    if id_inserito:
        st.session_state.session_id = id_inserito
        storico_db = engine._get_mongo_history(id_inserito).messages
        st.session_state.messages = []
        if not storico_db:
            st.session_state.messages = [{"role": "assistant", "content": INCIPIT}]
        else:
            for msg in storico_db:
                ruolo = "user" if msg.type == "human" else "assistant"
                st.session_state.messages.append({"role": ruolo, "content": msg.content})
        st.session_state.attesa_dadi = False

def esci_partita():
    for key in list(st.session_state.keys()):
        del st.session_state[key]

# --- 2. SIDEBAR (Dashboard Avanzata) ---
with st.sidebar:
    st.title("☠️ Portale dell'Abisso")
    st.markdown("---")
    
    if "session_id" not in st.session_state:
        # Menu di Login (rimane uguale)
        st.subheader("Inizia l'Avventura")
        if st.button("🩸 Nuova Partita", use_container_width=True):
            avvia_nuova_partita()
            st.rerun()
        
        st.markdown("---")
        id_input = st.text_input("ID Partita:", placeholder="es. partita_1234abcd")
        if st.button("Carica", use_container_width=True):
            carica_partita(id_input)
            st.rerun()
            
    else:
        # --- DASHBOARD DI GIOCO ---
        # Recuperiamo lo stato aggiornato dal DB tramite l'engine
        stato = engine.get_game_state(st.session_state.session_id)
        
        # A. Sanità Mentale con Feedback Visivo
        s = stato.get("sanita", 100)
        st.subheader(f"🧠 Sanità: {s}%")
        bar_color = "red" if s < 30 else "orange" if s < 60 else "green"
        st.progress(max(0, min(s, 100)) / 100)
        
        # B. Il Party (Dinamico)
        st.markdown("---")
        st.subheader("👥 Compagni")
        party = stato.get("party", [])
        if party:
            for membro in party:
                st.write(f"• {membro}")
        else:
            st.caption("Sei solo nell'oscurità.")

        # C. Inventario
        st.markdown("---")
        inv = stato.get("inventory", [])
        st.info(f"🎒 Zaino:\n{', '.join(inv) if inv else 'Vuoto'}")
        
        st.markdown("---")
        st.caption(f"ID: `{st.session_state.session_id}`")
        if st.button("🚪 Abbandona", type="primary", use_container_width=True):
            esci_partita()
            st.rerun()

# --- 3. INTERFACCIA CHAT E LOGICA DADI ---
if "session_id" in st.session_state:
    st.title("☠️ L'Abisso")

    # Visualizzazione Storico
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # --- MECCANICA LANCIO DADI ---
    if st.session_state.get("attesa_dadi"):
        st.error("🎲 L'azione è incerta. L'Abisso richiede un tributo al caso.")
        
        # Un solo bottone!
        if st.button("LANCIA IL DADO (D20)", use_container_width=True):
            risultato = random.randint(1, 20)
            
            # 1. Chiamiamo l'engine per aggiornare i dati (Sanità, ecc.)
            evento = engine.risolvi_lancio_dado(st.session_state.session_id, risultato)
            
            # 2. Mostriamo il feedback visivo immediato
            if risultato <= 5:
                st.error(f"⚠️ Risultato: {risultato} - {evento}")
            elif risultato >= 15:
                st.success(f"🌟 Risultato: {risultato} - {evento}")
            else:
                st.warning(f"⚖️ Risultato: {risultato} - {evento}")

            # 3. Inviamo l'esito al DM per la narrazione
            with st.spinner("L'Abisso osserva il risultato..."):
                # Passiamo il risultato al LLM (gioca_turno ora restituisce un dict)
                res_dice = gioca_turno(f"[RISULTATO DADO: {risultato} - {evento}]", st.session_state.session_id)
                
                # Aggiungiamo i messaggi alla chat
                st.session_state.messages.append({"role": "user", "content": f"🎲 Lancio Dado: {risultato}"})
                st.session_state.messages.append({"role": "assistant", "content": res_dice["testo"]})
                
                # Reset dello stato
                st.session_state.attesa_dadi = False
                st.rerun()
    # --- INPUT NORMALE (Attivo solo se non aspettiamo i dadi) ---
    else:
        if prompt := st.chat_input("Cosa fai?"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)

            with st.chat_message("assistant"):
                with st.spinner("L'Abisso sussurra..."):
                    # Ora gioca_turno restituisce un DIZIONARIO {"testo": ..., "dice": bool}
                    res = gioca_turno(prompt, st.session_state.session_id)
                    st.write(res["testo"])
                    st.session_state.messages.append({"role": "assistant", "content": res["testo"]})
                    
                    # Se il DM ha richiesto un dado, attiviamo il blocco al prossimo giro
                    if res.get("dice"):
                        st.session_state.attesa_dadi = True
                        st.rerun()

else:
    st.markdown("<h2 style='text-align: center; color: gray; margin-top: 20%;'>Varcate la soglia dal menu laterale.</h2>", unsafe_allow_html=True)