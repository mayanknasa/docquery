import io

from pypdf import PdfReader


def extract_text(filename: str, data: bytes) -> str:
    """Blocking function: call it with asyncio.to_thread from async code."""
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return data.decode("utf-8", errors="ignore")
