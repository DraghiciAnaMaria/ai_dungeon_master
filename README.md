# 🎲 AI Dungeon Master: Architettura RAG e Agenti Autonomi

##  Panoramica del Progetto
*AI Dungeon Horror Master* è un agente conversazionale basato su LLM che funge da narratore dinamico per sessioni di gioco di ruolo. Sotto l'interfaccia ludica, il sistema implementa un'architettura **Agentica e Cloud-Ready** progettata per replicare scenari reali, come l'interrogazione intelligente di documenti e l'analisi di stati operativi in tempo reale.

## Stack Tecnologico e Architettura
* **LLM Engine & Open Source Inference (GroqCloud):** Il "cervello" dell'agente è alimentato da modelli open-source allo stato dell'arte (es. LLaMA 3). Per l'inferenza è stata scelta l'infrastruttura **Groq**, che garantisce latenze minime e un'ottimizzazione dei costi (FinOps). Grazie all'API compatibility, il codice implementa l'SDK ufficiale di `openai`: questo garantisce uno standard industriale e annulla il *vendor lock-in*, permettendo uno switch immediato verso altri provider cloud.
* **Retrieval-Augmented Generation (RAG):** Elaborazione di manuali PDF convertiti in embedding semantici e interrogazione tramite Database Vettoriale per evitare "allucinazioni".
* **Agentic Workflow e Tool Calling:** Orchestrazione dell'LLM (tramite LangChain/LlamaIndex) per invocare funzioni Python esterne (es. lancio di dadi, aggiornamento statistiche), simulando l'interazione con API aziendali.
* **Gestione dello Stato Temporale (MongoDB):** Tracciamento dei KPI del giocatore ("Sanità Mentale", Inventario) in tempo reale su database NoSQL.
* **Prompt Engineering:** Controllo rigido dell'output per mantenere il tono horror psicologico.

**Obiettivo Tecnico:** Dimostrare lo sviluppo di un flusso AI end-to-end, dall'elaborazione del dato non strutturato all'interazione dinamica con l'utente finale