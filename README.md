# Jeffrey – Local Butler AI

**Author:** Laszlo Czako  
**Status:** Early MVP – Concept + reference implementation

Jeffrey is a **local, on-device AI butler** designed to run on your own computer, with:

- Persistent, on-disk memory  
- A defined British-butler personality (dry, sarcastic, loyal)  
- The ability to later integrate with:
  - Local or cloud LLMs
  - File access
  - System automations and scripts

This repository serves as both a **technical prototype** and a **timestamped public record** of the architecture and concept.

---

## Features (Current MVP)

- CLI-based assistant  
- Stores long-term facts in `memory.json`  
- Configurable personality and name via `config.json`  
- Uses OpenAI API for the language model (for now)  

---

## Getting Started

1. Clone the repo:

   ```bash
   git clone https://github.com/lczako-eng/jeffrey-local-butler-ai.git
   cd jeffrey-local-butler-ai
