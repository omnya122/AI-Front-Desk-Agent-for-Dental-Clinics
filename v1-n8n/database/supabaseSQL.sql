create extension if not exists vector;

create table clinic_docs (
  id bigserial primary key,
  content text,
  metadata jsonb,
  embedding vector(3072)
);

create or replace function match_clinic_docs (
  query_embedding vector(3072),
  match_count int default 5
) returns table (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language sql stable
as $$
  select
    id, content, metadata,
    1 - (clinic_docs.embedding <=> query_embedding) as similarity
  from clinic_docs
  order by clinic_docs.embedding <=> query_embedding
  limit match_count;
$$;