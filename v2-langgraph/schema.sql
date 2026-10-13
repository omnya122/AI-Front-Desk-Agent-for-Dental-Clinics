CREATE EXTENSION IF NOT EXISTS vector;

-- Structured facts: exact lookups, never embedded -------------------------
CREATE TABLE IF NOT EXISTS pricing (
    procedure    text PRIMARY KEY,
    price_egp    int  NOT NULL,
    duration_min int  NOT NULL
);

CREATE TABLE IF NOT EXISTS hours (
    day_index int PRIMARY KEY,          -- Monday = 0 ... Sunday = 6
    day       text NOT NULL,
    opens     time,                     -- NULL = closed
    closes    time
);

CREATE TABLE IF NOT EXISTS doctors (
    name      text PRIMARY KEY,
    specialty text NOT NULL,
    days      text[] NOT NULL
);

CREATE TABLE IF NOT EXISTS insurance (
    provider text PRIMARY KEY,
    coverage text NOT NULL,
    notes    text
);

-- Prose knowledge: chunked + embedded --------------------------------------
CREATE TABLE IF NOT EXISTS doc_chunks (
    id          bigserial PRIMARY KEY,
    filename    text NOT NULL,
    file_hash   text NOT NULL,
    chunk_index int  NOT NULL,
    content     text NOT NULL,
    embedding   vector(768) NOT NULL
);
CREATE INDEX IF NOT EXISTS doc_chunks_embedding_idx ON doc_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS doc_chunks_filename_idx  ON doc_chunks (filename);

-- Bookings: UNIQUE(slot_start) is the final idempotency guarantee ----------
CREATE TABLE IF NOT EXISTS bookings (
    id           bigserial PRIMARY KEY,
    chat_id      bigint NOT NULL,
    slot_start   timestamptz NOT NULL UNIQUE,
    procedure    text,
    patient_name text NOT NULL,
    phone        text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- Operations --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS processed_updates (
    update_id bigint PRIMARY KEY,
    ts        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rate_events (
    chat_id bigint NOT NULL,
    ts      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS rate_events_chat_ts_idx ON rate_events (chat_id, ts);

CREATE TABLE IF NOT EXISTS escalations (
    id       bigserial PRIMARY KEY,
    ts       timestamptz NOT NULL DEFAULT now(),
    chat_id  bigint NOT NULL,
    question text,
    category text NOT NULL,
    layer    text NOT NULL,             -- emergency_gate | keyword_gate | agent | output_guard
    reason   text
);

CREATE TABLE IF NOT EXISTS turns (
    id          bigserial PRIMARY KEY,
    ts          timestamptz NOT NULL DEFAULT now(),
    chat_id     bigint NOT NULL,
    update_id   bigint,
    question    text,
    route       text,
    layer       text,
    category    text,
    confidence  real,
    escalated   boolean NOT NULL DEFAULT false,
    tokens_in   int NOT NULL DEFAULT 0,
    tokens_out  int NOT NULL DEFAULT 0,
    cost_usd    numeric(10,6) NOT NULL DEFAULT 0,
    latency_ms  int
);
