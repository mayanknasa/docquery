import asyncio
import uuid
from datetime import datetime, timezone

import numpy as np

from app.config import Settings
from app.schemas import AskOut, DocumentOut, SourceOut
from app.services.chunking import chunk_text
from app.services.extract import extract_text
from app.services.llm import LLMClient
from app.services.retrieval import top_k_chunks
from app.services.store import Chunk, DocMeta, Store


async def embed_in_parallel(llm: LLMClient, texts: list[str], batch_size: int, max_concurrency: int):
    """Split texts into batches and embed them concurrently, capped by a semaphore."""
    semaphore = asyncio.Semaphore(max_concurrency)

    async def run(batch: list[str]):
        async with semaphore:
            return await llm.embed(batch)

    batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]
    results = await asyncio.gather(*(run(b) for b in batches))  # gather keeps order
    return [vec for batch_result in results for vec in batch_result]


class EmptyDocumentError(Exception):
    pass


async def ingest_document(filename: str, data: bytes, store: Store, llm: LLMClient, s: Settings) -> DocumentOut:
    text = await asyncio.to_thread(extract_text, filename, data)  # blocking work off the event loop
    pieces = chunk_text(text, s.chunk_size, s.chunk_overlap)
    if not pieces:
        raise EmptyDocumentError()

    vectors = await embed_in_parallel(llm, pieces, s.embed_batch_size, s.max_concurrency)
    chunks = [Chunk(i, t, np.asarray(v, dtype=np.float32)) for i, (t, v) in enumerate(zip(pieces, vectors))]

    meta = DocMeta(
        doc_id=uuid.uuid4().hex,
        filename=filename,
        num_chunks=len(chunks),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    await store.save(meta, data, chunks)
    return DocumentOut(doc_id=meta.doc_id, filename=meta.filename, num_chunks=meta.num_chunks)


async def answer_question(doc_id: str, question: str, top_k: int, store: Store, llm: LLMClient) -> AskOut | None:
    if await store.get_meta(doc_id) is None:
        return None
    chunks = await store.get_chunks(doc_id)
    query_vec = (await llm.embed([question]))[0]
    hits = top_k_chunks(query_vec, chunks, top_k)
    answer = await llm.answer(question, [c.text for c, _ in hits])
    sources = [SourceOut(chunk_index=c.index, score=round(score, 4), snippet=c.text[:200]) for c, score in hits]
    return AskOut(answer=answer, sources=sources)
