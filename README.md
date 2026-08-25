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