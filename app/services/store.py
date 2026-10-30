import asyncio
from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass
class DocMeta:
    doc_id: str
    filename: str
    num_chunks: int
    created_at: str


@dataclass
class Chunk:
    index: int
    text: str
    embedding: np.ndarray


class Store(Protocol):
    async def save(self, meta: DocMeta, raw: bytes, chunks: list[Chunk]) -> None: ...

    async def get_meta(self, doc_id: str) -> DocMeta | None: ...

    async def get_chunks(self, doc_id: str) -> list[Chunk]: ...


class LocalStore:
    """In memory storage for local development and tests."""

    def __init__(self) -> None:
        self._meta: dict[str, DocMeta] = {}
        self._chunks: dict[str, list[Chunk]] = {}

    async def save(self, meta, raw, chunks) -> None:
        self._meta[meta.doc_id] = meta
        self._chunks[meta.doc_id] = chunks

    async def get_meta(self, doc_id):
        return self._meta.get(doc_id)

    async def get_chunks(self, doc_id):
        return self._chunks.get(doc_id, [])


class AwsStore:
    """Raw files go to S3. Metadata and chunk vectors go to one DynamoDB table.

    Table layout: pk = doc_id, sk = "META" or "CHUNK#00001".
    boto3 is blocking, so every call runs in a worker thread via asyncio.to_thread.
    """

    def __init__(self, region: str, bucket: str, table: str) -> None:
        import boto3

        self.bucket = bucket
        self.s3 = boto3.client("s3", region_name=region)
        self.table = boto3.resource("dynamodb", region_name=region).Table(table)

    async def save(self, meta, raw, chunks) -> None:
        await asyncio.to_thread(self._save, meta, raw, chunks)

    async def get_meta(self, doc_id):
        return await asyncio.to_thread(self._get_meta, doc_id)

    async def get_chunks(self, doc_id):
        return await asyncio.to_thread(self._get_chunks, doc_id)

    def _save(self, meta: DocMeta, raw: bytes, chunks: list[Chunk]) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=f"documents/{meta.doc_id}/{meta.filename}", Body=raw)
        with self.table.batch_writer() as batch:
            batch.put_item(
                Item={
                    "pk": meta.doc_id,
                    "sk": "META",
                    "filename": meta.filename,
                    "num_chunks": meta.num_chunks,
                    "created_at": meta.created_at,
                }
            )
            for c in chunks:
                batch.put_item(
                    Item={
                        "pk": meta.doc_id,
                        "sk": f"CHUNK#{c.index:05d}",
                        "text": c.text,
                        "embedding": c.embedding.astype(np.float32).tobytes(),
                    }
                )

    def _get_meta(self, doc_id: str) -> DocMeta | None:
        item = self.table.get_item(Key={"pk": doc_id, "sk": "META"}).get("Item")
        if not item:
            return None
        return DocMeta(doc_id, item["filename"], int(item["num_chunks"]), item["created_at"])

    def _get_chunks(self, doc_id: str) -> list[Chunk]:
        from boto3.dynamodb.conditions import Key

        chunks: list[Chunk] = []
        kwargs = {"KeyConditionExpression": Key("pk").eq(doc_id) & Key("sk").begins_with("CHUNK#")}
        while True:
            resp = self.table.query(**kwargs)
            for item in resp["Items"]:
                vec = np.frombuffer(item["embedding"].value, dtype=np.float32)
                chunks.append(Chunk(int(item["sk"].split("#")[1]), item["text"], vec))
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return chunks


def build_store(settings) -> Store:
    if settings.storage_backend == "aws":
        if not (settings.s3_bucket and settings.dynamodb_table):
            raise RuntimeError("S3_BUCKET and DYNAMODB_TABLE are required when STORAGE_BACKEND=aws")
        return AwsStore(settings.aws_region, settings.s3_bucket, settings.dynamodb_table)
    return LocalStore()
