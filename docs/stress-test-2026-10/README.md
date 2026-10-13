# Stress test, October 2026 — the data

The report is `docs/STRESS_TEST_2026-10.md`. This folder is what it was built from.

| File | What it holds |
|---|---|
| `scenarios.csv` | Every scenario: area, id, title, actor, verdict (PASS / FAIL / GAP / RISK), severity, and whether code was actually run |
| `findings.json` | Every finding the testers reported, by area, with repro, files, impact and fix — plus what the independent skeptics concluded: `kept`, `refuted`, or `not-checked`, with their evidence and the severity they settled on |
| `issues.json` | The 69 deduplicated root issues (I-01 … I-69) the report's section 4 lists, each with `sources` pointing back to `findings.json` as `area#index` |
| `gaps.json` | Capabilities the testers said were missing, as audited against the code: confirmed absent or not, what to build, and how urgent |
| `counts-and-critic.json` | The counts behind the report's tables, and the five areas the completeness critic found untested |

Redactions: every email address in tester-invented data is replaced with
`someone@example.invalid`, and one toll-free number that may be real is replaced.
Test card numbers and SINs are standard test values, not anyone's.

How it ran: test agents wrote and executed scenarios against the real code in
throwaway home folders (never the owner's data); independent skeptic agents then
reproduced each serious finding from scratch and tried to refute it. Engine calls
were simulated — no real Claude, ChatGPT or Ollama model was involved — and
nothing ran on a real Mac. See section 9 of the report.
