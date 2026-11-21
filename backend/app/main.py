from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .engine import answer_question
from .models import AskRequest
from .policies import list_documents, save_upload

app = FastAPI(title="CampusAnswer API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/documents")
def documents() -> list[dict]:
    return [document.model_dump() for document in list_documents()]


@app.post("/api/ask")
def ask(request: AskRequest) -> dict:
    try:
        return answer_question(request.question.strip(), request.prompt_version).model_dump()
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/documents/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    try:
        document = save_upload(file.filename or "", await file.read())
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return document.model_dump()
