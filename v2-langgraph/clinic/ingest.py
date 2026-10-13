"""Index data/docs/* into pgvector. Only files whose content hash changed are re-embedded.

    python -m clinic.ingest            # one pass
    python -m clinic.ingest --watch    # poll every 30 s (replaces the n8n Drive trigger)
"""
import asyncio
import hashlib
import sys
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import db
from .embeddings import embedder

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "docs"
# ~250 tokens per chunk with ~40 tokens of overlap: the documents are short and fact-dense.
_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)


async def sync_docs() -> dict[str, list[str]]:
    existing = {r["filename"]: r["file_hash"] for r in await db.fetch("SELECT DISTINCT filename, file_hash FROM doc_chunks")}
    files = {p.name: p for p in sorted(DOCS_DIR.iterdir()) if p.suffix in {".txt", ".md"}}
    stats: dict[str, list[str]] = {"indexed": [], "skipped": [], "removed": []}

    for name in set(existing) - set(files):
        await db.execute("DELETE FROM doc_chunks WHERE filename = %s", (name,))
        stats["removed"].append(name)

    for name, path in files.items():
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if existing.get(name) == digest:
            stats["skipped"].append(name)
            continue
        chunks = _splitter.split_text(text)
        vectors: list[list[float]] = []
        for i in range(0, len(chunks), 50):  # embed first: a failed API call must not wipe the old index
            vectors += await embedder("retrieval_document").aembed_documents(chunks[i:i + 50])
        async with db.pool().connection() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM doc_chunks WHERE filename = %s", (name,))
                for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
                    await conn.execute(
                        "INSERT INTO doc_chunks (filename, file_hash, chunk_index, content, embedding) "
                        "VALUES (%s, %s, %s, %s, %s::vector)",
                        (name, digest, idx, chunk, db.vector_literal(vec)),
                    )
        stats["indexed"].append(f"{name} ({len(chunks)} chunks)")
    return stats


async def main(watch: bool) -> None:
    await db.init_pool()
    try:
        while True:
            stats = await sync_docs()
            if stats["indexed"] or stats["removed"] or not watch:
                print(stats)
            if not watch:
                break
            await asyncio.sleep(30)
    finally:
        await db.close_pool()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main("--watch" in sys.argv))
