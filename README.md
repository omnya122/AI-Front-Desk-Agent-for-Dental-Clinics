# AI Front-Desk Agent for Dental Clinics

A Telegram assistant for a **fictional** dental clinic. It answers administrative questions (prices, hours,
doctors, insurance, policies, aftercare instructions), and escalates anything clinical to human staff instead of
giving medical advice.

I built it twice to compare a low-code approach with a code-first one.

| | [v1 – n8n](v1-n8n) | [v2 – LangGraph](v2-langgraph) |
|---|---|---|
| Orchestration | Visual n8n workflow | Python state graph (LangGraph 1.2) |
| Knowledge | Supabase vector store + Google Sheets | Postgres + pgvector, tables loaded from CSV |
| Safety | Keyword filter, agent flag, output check | Emergency and keyword gates before the LLM, agent flags, output guard, fixed (never model-written) handover message |
| Booking | – | Inline-button slot booking, idempotent confirm, validated phone numbers |
| Memory | n8n window memory | Postgres checkpointer (survives restarts) |
| Reliability | Basic error branch | Update de-duplication, per-chat rate limit, history repair, staff alerts |
| Evaluation | Manual testing | 54-question harness reporting admin answer rate, clinical refusal rate, latency and cost |

## Which version should I read?

- **[v1-n8n](v1-n8n)**: the original prototype. Good for seeing the workflow design, prompts and screenshots.
- **[v2-langgraph](v2-langgraph)**: the rebuild with booking, stronger safety layers and an evaluation harness.
  Start with its README for the architecture diagram, setup steps and results.

All data is fictional. This is a portfolio project and is not deployed for a real clinic.
