# AI Front-Desk Agent for Dental Clinics

A conversational agent that handles admin enquiries for a (fictional) dental clinic over Telegram, with a hard safety boundary preventing any clinical advice from ever reaching a patient. Built in n8n, backed by RAG over clinic policy documents and structured lookups for pricing/hours/insurance/doctors.

> **Note:** This uses entirely fictional clinic data (fake doctors, fake pricing, fake policies) and was never deployed for a real practice. It's a portfolio project demonstrating an agentic workflow with a safety-critical design constraint.

---

## Architecture

```
Telegram (user message)
      │
      ▼
   n8n webhook
      │
      ▼
 Layer 1: Emergency Check + Clinical Keyword Check (deterministic regex, pre-filter)
      │  (fails / clinical) ──────────────► Escalation chain (log → notify staff → user reply)
      ▼ (passes)
   AI Agent (Gemini) ── tools: search_clinic_docs, get_price, get_hours,
      │                        get_insurance, get_doctors, check_availability,
      │                        escalate_to_staff
      ▼
 Layer 3: Output Safety Check (post-generation, catches anything that slipped through)
      │  (fails) ──────────────────────────► Escalation chain
      ▼ (passes)
   Reply sent to user + turn logged
```

Knowledge layer: clinic policy PDFs → chunked → embedded (Google Gemini embeddings) → stored in Supabase/pgvector, retrieved via the `search_clinic_docs` tool. Structured data (pricing, hours, insurance, doctors) lives in Google Sheets and is queried directly rather than embedded — see below for why.

---

## The facts-vs-prose split

Clinic policy documents (what to bring to a first visit, cancellation policy, etc.) go through the vector store, because they're prose that benefits from semantic retrieval — a user might ask the same question ten different ways.

Pricing, hours, insurance, and doctor lists are **not** embedded. They're structured, small, and change independently of any "meaning" — embedding them adds retrieval uncertainty (approximate matches, wrong row picked) to data that should be looked up exactly. These are exposed to the Agent as direct lookup tools instead, with a "return everything, let the Agent match loosely" approach, since the Sheets nodes available don't support a native "contains" filter.

---

## The three-layer safety gate

This is the core design constraint of the project: **no clinical advice, ever, under any framing.**

1. **Layer 1 — Emergency Check + Clinical Keyword Check** (deterministic regex, before the Agent even runs). Catches obvious symptom/medication/emergency language up front, before any LLM call, so it can't be reasoned around.
2. **Layer 2 — Agent-level escalation.** The Agent itself carries an `escalate_to_staff` tool and a system prompt instructing it to hand off anything clinical it wasn't caught by Layer 1 — covers edge phrasing the regex misses.
3. **Layer 3 — Output Safety Check** (post-generation, after the Agent replies). A final check on the Agent's own output before it's sent, catching anything that slipped through generation.

Each layer feeds the same escalation chain: log the event → notify staff → send the user a graceful hand-off message, rather than a raw error.

---

## What's built

- Telegram bot wired to n8n, with text/non-text routing and `/start` handling
- Fictional clinic dataset: Google Sheet (Pricing / Hours / Insurance / Doctors) + policy documents in Drive
- RAG ingestion pipeline: Drive → chunk → embed (Gemini) → Supabase/pgvector
- AI Agent (Gemini) with windowed memory keyed on `chat.id`, 8 tools, structured output schema
- Three-layer clinical safety gate (see above), each layer logging to a shared sheet: `chat_id, question, category, confidence, escalated, tokens, cost`
- Structured lookup tools tested independently for pricing, hours, insurance, doctors

## Known bugs hit and fixed along the way

- IF-condition routing bug on text/non-text detection (wrong field checked)
- Vector dimension mismatch (768 vs 3072) between embedding models
- `.item` vs `.first()` handling breaking chat_id pairing inside the AI Agent node
- Boolean/string type mismatch and a smart-quote-vs-straight-quote matching bug in the Emergency Check
- A swapped-fields bug in the Emergency Check condition

---

## Cut for v1 / planned

- Appointment booking (Google Calendar integration, inline-keyboard slot selection, idempotency handling)
- Reschedule / cancel flows
- Payments
- Multi-clinic support
- Staff dashboard
- Per-user rate limiting
- Workflow-level error handling / retry policies

---

## Disclaimer

All clinic data (name, doctors, pricing, policies) is fictional and was created for this project. This system has not been deployed for, or tested against, a real dental practice.
