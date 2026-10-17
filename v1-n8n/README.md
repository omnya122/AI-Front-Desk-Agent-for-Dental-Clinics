# AI Front-Desk Agent for Dental Clinics (n8n version)

A Telegram bot that helps patients of a (fictional) dental clinic. It answers simple questions, books
appointments in Google Calendar, and never gives medical advice. Medical questions go to a staff member.

---

## What the bot can do

- Answer questions about **prices, opening hours, doctors and insurance** (from Google Sheets).
- Answer questions about **clinic rules, parking, payment and aftercare** (from text documents).
- **Book an appointment** in Google Calendar.
- Reply in **English or Arabic**.
- **Send medical questions to staff**, and save them in an Escalation Log sheet.

---

## How a message flows

```
Patient message (Telegram)
      |
      v
 Safety check 1: emergency words and medical words (simple rules, before the AI)
      |  medical -------------------> Fixed reply to patient + alert to staff + log row
      v  normal
   AI Agent (Gemini)  -- uses tools: prices, hours, doctors, insurance,
      |                  clinic documents, check_slot, book_appointment, escalate_to_staff
      v
 Safety check 2: look at the AI answer before sending
      |  unsafe --------------------> Fixed reply to patient + alert to staff + log row
      v  safe
   Reply sent to the patient
```

**Safety checks.** The main rule of this project is: no medical advice, ever.
1. **Simple rules first.** Words like "pain", "swelling" or "antibiotics" (English and Arabic) stop the message
   before it reaches the AI.
2. **The agent can hand over.** If a medical question gets past the rules, the agent can still send it to staff.
3. **Check the answer.** Before sending, the answer is checked again for medical advice.

All three checks use the same hand-over steps: save a log row, alert staff, and send the patient a polite message.

---

## Booking an appointment

Booking uses a second workflow (**Book Appointment**) that the agent calls like a tool. The checks are done in
code, not by the AI, because the AI can make mistakes with dates and times.

How a booking works:
1. The patient says they want an appointment. The agent asks for the **day**.
2. The agent tells the patient the opening hours for that day and asks for a **time**.
   It does **not** suggest times on its own.
3. The agent calls `check_slot`. The workflow checks:
   - the day is not a closed day (Friday),
   - the whole appointment fits inside the opening hours,
   - the time is not in the past,
   - the time is free in Google Calendar.
4. If the time is free, the agent asks for the **name and phone number**. The phone number must be an Egyptian
   mobile number (11 digits, starting with 010, 011, 012 or 015). If it is wrong, the workflow refuses it and the
   agent asks again.
5. The agent repeats the details and asks the patient to confirm.
6. After the patient says yes, the agent calls `book_appointment`. The workflow checks everything again and then
   creates the event in Google Calendar.
7. The agent only says "booked" when the workflow answers `BOOKED`. If the answer is `SLOT_TAKEN` or `INVALID`,
   the agent explains and asks for another time.

---

## Where the data lives

- **Prices, hours, doctors, insurance:** Google Sheets. These are small tables. This gives exact answers.
- **Clinic documents** (rules, parking, payment, aftercare): split into small pieces, turned into vectors with
  Gemini embeddings, and stored in Supabase. The agent searches them with `search_clinic_docs`.
- **Escalation Log:** a Google Sheet with one row for every message sent to staff.

---

## Files in this folder

| Folder or file | What it is |
|---|---|
| `workflows/Dental_Clinic_Agent.json` | Main workflow (Telegram, safety checks, AI agent, replies) |
| `workflows/Book Appointment.json` | Booking workflow (checks the time and phone, creates the calendar event) |
| `workflows/Clinic_Knowledge_Base_Ingestion.json` | Loads the clinic documents into the vector store |
| `prompts/system_prompt.md` | The agent instructions |
| `data/` | Fictional clinic data (CSV and text files) |
| `database/supabaseSQL.sql` | SQL to create the vector table |
| `screenshots/` | Workflows desing and some examples |

---

## How I ran it locally

- **Docker:** I ran n8n in a Docker container on my own computer.
- **ngrok:** Telegram can only send messages to a public HTTPS address. ngrok gives my local n8n a public
  address. I set it as `WEBHOOK_URL` for n8n, so the Telegram Trigger could register its webhook.
- If you want to try it yourself, start ngrok first, set `WEBHOOK_URL` to the ngrok address, then start n8n
  and publish the workflows.
- The free ngrok address changes each time it restarts. After a restart, update `WEBHOOK_URL` and publish the
  workflow again.

---

## How to set it up

1. Import the three workflows into n8n.
2. Create credentials for Telegram, Google (Sheets, Drive and Calendar), Gemini and Supabase.
3. Run `database/supabaseSQL.sql` in Supabase.
4. Upload the sheets and documents from `data/` to Google Drive, then run the ingestion workflow once.
5. In the main workflow, open the `check_slot` and `book_appointment` tool nodes and select the
   **Book Appointment** workflow.
6. **Publish both** the main workflow and the booking workflow. n8n will not run a workflow that is not active.

Credentials and IDs are not included in this repo. You must use your own.

---

## Problems I hit and fixed

- The AI offered times that were already taken, or said "booked" without booking. **Fix:** a separate workflow
  checks the calendar and the opening hours in code, and the agent must wait for its answer.
- A wrong phone number (for example, 10 or 13 digits) was accepted. **Fix:** the booking workflow checks the number.
- The AI sometimes returned an empty answer and nothing was sent. **Fix:** turn on Retry On Fail for the agent and
  send a short fallback message if it still fails.
- Telegram send nodes failed on a bad connection. **Fix:** Retry On Fail on the send nodes.

---

## What is not included

- Changing or cancelling an appointment (the bot sends these requests to staff).
- Payments, many clinics, a staff dashboard.
- Rate limits per user.

For a version with slot buttons, a database, more safety checks and automatic tests, see the
[LangGraph version](../v2-langgraph).

---

## Disclaimer

All clinic data (name, doctors, prices, rules) is fictional and was created for this project. The system has not
been used or tested in a real dental clinic.
