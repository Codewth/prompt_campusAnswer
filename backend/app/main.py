import os

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .auth import AuthenticatedUser, require_admin, require_user, revoke_firebase_refresh_tokens
from .engine import GeminiUnavailableError, answer_question
from .models import AskRequest, ProfileSettingsUpdate, ProfileUpdate, StudentProfileResponse
from .official_index import OfficialIndexUnavailableError, list_official_documents
from .policies import list_documents, save_upload
from .profiles import get_profile, save_profile, save_theme
from .revocations import revoke_token

app = FastAPI(title="CampusAnswer API", version="1.0.0")


DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
]


def _cors_origins() -> list[str]:
    configured = os.getenv("CAMPUSANSWER_CORS_ORIGINS", "").strip()
    if not configured:
        return DEFAULT_CORS_ORIGINS
    origins = [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    if not origins or "*" in origins:
        raise ValueError("CAMPUSANSWER_CORS_ORIGINS must contain explicit origins and cannot include '*'.")
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/auth/me")
def current_user(user: AuthenticatedUser = Depends(require_user)) -> dict:
    profile = get_profile(user.uid, user.email, user.picture, user.name)
    return {**profile, "is_admin": user.is_admin}


@app.get("/api/profile", response_model=StudentProfileResponse)
def student_profile(user: AuthenticatedUser = Depends(require_user)) -> dict:
    return get_profile(user.uid, user.email, user.picture, user.name)


@app.put("/api/profile", response_model=StudentProfileResponse)
def update_student_profile(
    request: ProfileUpdate,
    user: AuthenticatedUser = Depends(require_user),
) -> dict:
    return save_profile(user.uid, request, user.email, user.picture)


@app.patch("/api/profile/settings", response_model=StudentProfileResponse)
def update_profile_settings(
    request: ProfileSettingsUpdate,
    user: AuthenticatedUser = Depends(require_user),
) -> dict:
    return save_theme(user.uid, request.theme, user.email, user.picture, user.name)


@app.post("/api/auth/logout")
def logout(
    authorization: str | None = Header(default=None),
    user: AuthenticatedUser = Depends(require_user),
) -> dict:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Google sign-in is required.")
    revoke_token(token.strip(), user.uid, user.token_expires_at)
    revoke_firebase_refresh_tokens(user.uid)
    return {"status": "signed_out"}


@app.get("/api/documents")
def documents(user: AuthenticatedUser = Depends(require_user)) -> list[dict]:
    documents = [*list_documents(), *list_official_documents()]
    return [document.model_dump() for document in documents]


@app.post("/api/ask")
def ask(request: AskRequest, user: AuthenticatedUser = Depends(require_user)) -> dict:
    try:
        return answer_question(
            request.question.strip(),
            request.prompt_version,
            request.collection,
            request.history,
        ).model_dump()
    except OfficialIndexUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except GeminiUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/documents/upload")
async def upload(file: UploadFile = File(...), user: AuthenticatedUser = Depends(require_admin)) -> dict:
    try:
        document = save_upload(file.filename or "", await file.read())
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return document.model_dump()
