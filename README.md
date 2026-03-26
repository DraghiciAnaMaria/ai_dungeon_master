# 🎲 AI Dungeon Master: Architettura RAG e State Management

## Panoramica del Progetto
**AI Dungeon Horror Master** è un agente conversazionale basato su LLM che funge da narratore dinamico per sessioni di gioco di ruolo. 

Il progetto nasce con un focus primario sullo **sviluppo backend e sull'ingegneria dei dati**, relegando il frontend a pura interfaccia di visualizzazione. Sotto la veste ludica, il sistema implementa un'architettura Agentica e Cloud-Ready progettata per risolvere sfide reali: l'interrogazione semantica di documenti non strutturati, la persistenza del contesto e l'aggiornamento autonomo di stati operativi complessi in tempo reale.

---

##  Ecosistema Dati e Architettura Backend

### Triangolazione dei Database (NoSQL vs. Vettoriali vs. SQL)
Il progetto ha richiesto il superamento del classico modello relazionale (SQL), troppo rigido per l'imprevedibilità del testo generativo, adottando un approccio ibrido all'avanguardia:
* **Database NoSQL (MongoDB):** Scelto per la sua natura *document-oriented* (BSON/JSON), si è rivelato ideale per salvare in tempo reale la cronologia dei messaggi e lo stato dinamico e mutabile della partita (Inventario, Sanità Mentale, Party).
* **Database Vettoriale (FAISS):** Utilizzato per archiviare gli *embeddings* (rappresentazioni numeriche vettoriali) dei manuali di gioco, permettendo la ricerca per affinità semantica e non per semplici keyword esatte.

###  Retrieval-Augmented Generation (RAG)
Elaborazione di manuali PDF convertiti in vettori per iniettare dinamicamente il contesto ("Lore" e regole) nel prompt di sistema prima di ogni interazione. Questo ancoraggio semantico azzera le "allucinazioni" dell'IA, costringendola a rispettare rigorosamente i vincoli del mondo di gioco forniti nei documenti narrativi.

###  Gestione della Memoria con LangChain
Risoluzione del problema nativo di "amnesia" degli LLM (modelli nativamente *stateless*) tramite l'implementazione di `MongoDBChatMessageHistory` tramite il framework LangChain. Questo garantisce la coerenza narrativa multi-turno e la persistenza delle sessioni a lungo termine.

###  Aggiornamento Autonomo dello Stato (Agentic Workflow)
L'IA è stata istruita, tramite tecniche di *Prompt Engineering* avanzato, a generare tag di sistema invisibili all'utente (es. `[ADD: Chiave]`, `[SANITY_LOSS: 15]`). Il backend Python intercetta queste stringhe tramite Espressioni Regolari (Regex) ed esegue automaticamente operazioni CRUD sul database MongoDB. Questo rende l'LLM un vero e proprio **motore decisionale attivo**, elevandolo da semplice chatbot ad Agente Autonomo.

###  Infrastruttura API e Zero Vendor Lock-in
Il "cervello" dell'agente è alimentato da modelli open-source allo stato dell'arte (es. LLaMA 3) eseguiti tramite l'infrastruttura di inferenza **GroqCloud** per garantire latenze minime e ottimizzazione dei costi. Sfruttando la compatibilità con lo standard dell'SDK di `openai`, il codice sorgente è totalmente agnostico: è possibile migrare da Groq, a OpenAI, fino a server proprietari H2O modificando esclusivamente le variabili d'ambiente (URL base e chiave API), garantendo lo **Zero Vendor Lock-in**.

---

##  Stack Tecnologico Principale
* **Linguaggio:** Python
* **Framework AI:** LangChain
* **Database:** MongoDB (NoSQL), FAISS (Vector DB)
* **LLM Provider:** GroqCloud / OpenAI Compatible API
* **Architettura Core:** RAG, Agentic Workflow, REST API
