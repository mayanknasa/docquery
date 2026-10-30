import numpy as np

from app.services.store import Chunk


def top_k_chunks(query_vec: list[float], chunks: list[Chunk], k: int) -> list[tuple[Chunk, float]]:
    """Return the k chunks most similar to the query, using cosine similarity."""
    if not chunks:
        return []
    q = np.asarray(query_vec, dtype=np.float32)
    matrix = np.vstack([c.embedding for c in chunks])
    sims = (matrix @ q) / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(q) + 1e-9)
    best = np.argsort(-sims)[:k]
    return [(chunks[i], float(sims[i])) for i in best]
