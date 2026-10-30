from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    doc_id: str
    filename: str
    num_chunks: int


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=10)


class SourceOut(BaseModel):
    chunk_index: int
    score: float
    snippet: str


class AskOut(BaseModel):
    answer: str
    sources: list[SourceOut]
