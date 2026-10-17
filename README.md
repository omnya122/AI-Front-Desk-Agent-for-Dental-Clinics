# AI Front-Desk Agent for Dental Clinics

A Telegram bot for a **fictional** dental clinic. It answers simple questions (prices, opening hours, doctors,
insurance, clinic rules). It can also book appointments. If a patient asks a medical question, the bot does not
answer. It passes the question to a staff member.

I built it twice, so I could compare two ways of working: a visual tool (n8n) and code (Python).

| | [v1 - n8n](v1-n8n) | [v2 - LangGraph](v2-langgraph) |
|---|---|---|
| How it is built | Visual workflow in n8n | Python code with LangGraph |
| Where the data lives | Google Sheets and a Supabase vector store | Postgres database with pgvector |
| Safety checks | Keyword check, agent check, answer check | Checks before and after the AI, plus fixed hand-over messages |
| Booking | Google Calendar. The slot is checked and booked in code | Slot buttons in Telegram, saved in the database |
| Memory | n8n chat memory | Saved in Postgres (kept after a restart) |
| Testing | Manual test questions | 54 test questions with automatic scores |

## Which version should I read first?

- **[v1 - n8n](v1-n8n)**: the first version. Good for seeing the workflow, the prompt and screenshots.
- **[v2 - LangGraph](v2-langgraph)**: the second version. It has more safety checks and a test script.
  Its README explains how to set it up and shows the results.

All data is fictional. This is a portfolio project. It is not used by a real clinic.
