# JEFFEREY — Personal AI Shadow

**Author / sole inventor:** Laszlo Czako
**Status:** working connector, installable by double-click, adversarially audited

> **Owner: read [`START_HERE.md`](START_HERE.md).** Preparing the drive,
> installing, your photographs, your voice, and seeing what left the house —
> in order, one double-click each.
> Engineers and agents: [`HANDOVER.md`](HANDOVER.md) and
> [`docs/MASTER_BUILD_LIST.md`](docs/MASTER_BUILD_LIST.md).

*The intelligence is rented. The conscience is owned.*

---

## The original concept note (2025)

**Status then:** Early MVP – Concept + reference implementation

Jeffrey is a **local, on-device AI butler** designed to run on your own computer, with:

- Persistent, on-disk memory  
- A defined British-butler personality (dry, sarcastic, loyal)  
- The ability to later integrate with:
  - Local or cloud LLMs
  - File access
  - System automations and scripts

This repository serves as both a **technical prototype** and a **timestamped public record** of the architecture and concept.

---

## ⚡ The Agent Connector (new)

**[`connector/`](connector/)** — JEFFEREY's first shipping form, per the
[public build spec](https://github.com/lczako-eng/Jeffrey-AI-Butler/blob/main/docs/JEFFEREY_TO_BE_BUILT.md):
an MCP server that plugs JEFFEREY's owned conscience into Claude and other
MCP-capable engines. Priorities with confidence scores, corrections as the
curriculum, facts separate from values, the Directive Pack — a conscience
you own, riding whichever engine is best.

*The intelligence is rented. The conscience is owned.*

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
