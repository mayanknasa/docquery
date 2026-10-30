from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.schemas import AskIn, AskOut, DocumentOut
from app.security import require_api_key
from app.services.pipeline import EmptyDocumentError, answer_question, ingest_document

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(request: Request, file: UploadFile = File(...)):
    state = request.app.state
    data = await file.read()
    if len(data) > state.settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")
    try:
        return await ingest_document(file.filename or "upload.txt", data, state.store, state.llm, state.settings)
    except EmptyDocumentError:
        raise HTTPException(status_code=422, detail="No readable text found in the file")


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(doc_id: str, request: Request):
    meta = await request.app.state.store.get_meta(doc_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentOut(doc_id=meta.doc_id, filename=meta.filename, num_chunks=meta.num_chunks)


@router.post("/{doc_id}/ask", response_model=AskOut)
async def ask(doc_id: str, body: AskIn, request: Request):
    state = request.app.state
    result = await answer_question(
        doc_id, body.question, body.top_k or state.settings.top_k, state.store, state.llm
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return result
