import hashlib
import re
from typing import Protocol

import numpy as np

SYSTEM_PROMPT = (
    "You answer questions using only the provided context. "
    "If the context does not contain the answer, say you could not find it in the document. "
    "Cite context numbers like [1] when you use them."
)


class LLMClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def answer(self, question: str, contexts: list[str]) -> str: ...


class MockLLM:
    """Deterministic offline stand in so the app and tests run without any API key.

    Embeddings are a hashed bag of words, so similar wording gives similar vectors.
    """

    DIM = 256

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t).tolist() for t in texts]

    async def answer(self, question: str, contexts: list[str]) -> str:
        if not contexts:
            return "I could not find that in the document."
        return f"[mock answer] Most relevant passage: {contexts[0]}"

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.DIM, dtype=np.float32)
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            bucket = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.DIM
            vec[bucket] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec


class OpenAILLM:
    def __init__(self, api_key: str, embedding_model: str, chat_model: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key)
        self.embedding_model = embedding_model
        self.chat_model = chat_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self.client.embeddings.create(model=self.embedding_model, input=texts)
        return [item.embedding for item in resp.data]

    async def answer(self, question: str, contexts: list[str]) -> str:
        context = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(contexts))
        resp = await self.client.chat.completions.create(
            model=self.chat_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
            ],
        )
        return resp.choices[0].message.content or ""


def build_llm(settings) -> LLMClient:
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAILLM(settings.openai_api_key, settings.embedding_model, settings.chat_model)
    return MockLLM()
