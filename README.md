# AI-Front-Desk-Agent-for-Dental-Clinics
Telegram‑based conversational agent in n8n for appointment booking and administrative enquiries

## Knowledge Layer
This project uses two separate n8n workflows:
1. **Dental Clinic Agent** — the main chatbot. Handles Telegram messages and replies to users.
2. **Clinic Docs Ingestion** — a separate, one-time/background workflow. Reads the clinic's policy documents from Google Drive and loads them into a searchable database.

### Why two data paths instead of one
The agent answers questions in two different ways, depending on the type of question:
- **Exact facts** (prices, hours, insurance coverage) are looked up directly from a Google Sheet. These have one correct answer, so a direct lookup is used — no AI guessing involved.
- **Policy questions** (pre-op instructions, aftercare, cancellation policy, etc.) are answered using RAG (Retrieval-Augmented Generation): the documents are split into small chunks, converted into embeddings (number representations of meaning) using Google Gemini, and stored in a Postgres database (Supabase) with the pgvector extension. When a user asks a question, their question is also converted into an embedding, and the system finds the stored chunk with the closest meaning to return as the answer.

Keeping these two paths separate avoids a common RAG mistake: letting the AI "guess" an exact number (like a price) from a fuzzy text search, which can produce a confident but wrong answer.

### A real bug I hit and fixed
While setting up the vector database, I initially created the Supabase table expecting 768-dimensional embeddings, based on Google's documentation for their default embedding model. When running the ingestion workflow, it failed with:

`Error inserting: expected 768 dimensions, not 3072`

The embedding model I was actually using (`gemini-embedding-001`) was returning 3072-dimension vectors instead of 768. I fixed this by updating the Supabase table and search function to expect `vector(3072)` instead, matching the model's real output. This is a good example of why it's worth verifying assumptions about a third-party API's actual behavior instead of trusting documentation defaults blindly.

## Agent Layer

The main chatbot workflow uses an n8n AI Agent (tool-calling) node as its core — rather than the AI generating answers from its own knowledge, it decides which tool to call based on the user's question, and answers using the real data that tool returns.

### Tools

The agent has 8 tools available, split across the two data paths described above:

- **`search_clinic_docs`** — searches the Supabase vector store for relevant policy document chunks (pre-op instructions, aftercare, cancellation policy, location, payment methods).
- **`get_price`**, **`get_hours`**, **`get_insurance_coverage`**, **`get_doctor_info`** — read directly from the Google Sheet's Pricing, Hours, Insurance, and Doctors tabs. These tools return the full table rather than filtering by an exact match, since users rarely phrase a request exactly as it's written in a spreadsheet (e.g., "checkup" vs. "Checkup & Consultation") — the agent itself handles the fuzzy matching, which suits a small reference table far better than a database-level "contains" filter would.
- **`check_availability`** — reads events from a dedicated Google Calendar to check appointment availability. A minimal version today; full slot-booking logic is a later addition.
- **`escalate_to_staff`** — sends a message to a staff Telegram chat when a question needs human attention. Uses n8n's `$fromAI()` function so the agent generates its own short reason for the escalation at call time, rather than relying on a static message.
- **`book_appointment`** — a stub for now; creates a calendar event once full booking logic is built.

### Memory

Conversation memory is a windowed buffer keyed on the Telegram `chat.id`, holding the last 10 exchanges. This keeps each user's conversation separate from every other user's, without needing to store an unbounded, ever-growing history.

### Structured output

The agent's response is forced into a fixed schema rather than free text:

```json
{
  "answer": "string",
  "category": "string",
  "confidence": "number",
  "clinical_flag": "boolean",
  "sources": ["string"]
}
```

This is what makes the next layer of the project possible: a downstream safety check can reliably read `clinical_flag` and scan `answer` for red-flag content, and an escalation log can record `category` and `chat_id` cleanly — none of which would be practical to do reliably by parsing an unstructured sentence.

### A real bug I hit and fixed

The AI Agent node breaks n8n's normal item-pairing once a tool call happens mid-execution — referencing the original Telegram chat ID downstream using the usual `$json.message.chat.id` (or even `.item.json...`) pattern resolved to empty, causing Telegram to reject the send with `Bad Request: chat_id is empty`. The fix was to reach back to the trigger node explicitly and take the first item rather than the paired one: `$('Telegram Trigger').first().json.message.chat.id`. This was a useful reminder that AI Agent nodes don't preserve data flow the same way regular nodes do, and any value needed downstream of an agent call has to be deliberately reached for, not assumed to still be in `$json`.