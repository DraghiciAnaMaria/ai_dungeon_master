import streamlit as st

def apply_gothic_style():
    """Inietta CSS per atmosfera Goth con controlli sidebar sempre visibili"""
    st.markdown(
        """
        <style>
        /* --- 1. FONTS & ANIMAZIONI (Solo Titolo Principale) --- */
        @import url('https://fonts.googleapis.com/css2?family=Almendra:ital,wght@0,400;0,700;1,400&display=swap');

        /* Titolo Principale (H1 fuori dalla sidebar) */
        #l-abisso-dungeon-master {
            font-family: 'Almendra', serif !important;
            color: #b01c2e !important;
            text-align: center;
        }
        
        /* Titolo Sidebar (Statico) */
        [data-testid="stSidebar"] h1 {
            font-family: 'Almendra', serif ;
            color: #b01c2e ;
            text-shadow: 1px 1px 2px #000000;
        }

        /* --- 2. CONTROLLI SIDEBAR SEMPRE VISIBILI --- */
        /* Forza il pulsante di apertura/chiusura a essere visibile */
        [data-testid="stSidebarCollapseButton"] {
            visibility: visible ;
            opacity: 1 ;
            color: #b01c2e t; /* Colore rosso per il pulsante */
            background-color: rgba(26, 26, 46, 0.5) ;
            border-radius: 50%;
        }

        /* --- 3. LAYOUT & CHAT (Goth) --- */
        [data-testid="stSidebar"] {
            border-right: 2px solid #b01c2e;
        }

        .stChatMessage {
            border-radius: 15px;
            border: 1px solid #1a1a2e;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        
        .stChatMessage:hover {
            transform: translateY(-2px);
            box-shadow: 0 0 10px rgba(176, 28, 46, 0.4);
        }

        /* Focus sul box di input */
        [data-testid="stChatInput"] > div:focus-within {
            border: 2px solid #b01c2e;
            box-shadow: 0 0 10px rgba(176, 28, 46, 0.8) ;
        }
        
        [data-testid="stChatInput"] {
            border: none ;
        }

        </style>
        """,
        unsafe_allow_html=True
    )