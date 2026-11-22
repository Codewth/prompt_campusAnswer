import os
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import firebase_admin
import jwt
from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from firebase_admin.exceptions import FirebaseError
from google.auth.exceptions import DefaultCredentialsError
from requests import RequestException

from .revocations import is_token_revoked

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_app_lock = Lock()
FIREBASE_SIGNING_KEYS_URL = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
_signing_keys = jwt.PyJWKClient(FIREBASE_SIGNING_KEYS_URL, cache_keys=True)


@dataclass(frozen=True)
class AuthenticatedUser:
    uid: str
    email: str | None
    name: str | None
    picture: str | None
    is_admin: bool
    token_expires_at: int


def _firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    with _app_lock:
        try:
            return firebase_admin.get_app()
        except ValueError:
            pass

        service_account_path = (
            os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        )
        project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
        try:
            if service_account_path:
                path = Path(service_account_path).expanduser()
                if not path.is_file():
                    raise HTTPException(
                        status_code=503,
                        detail="Firebase service-account file was not found. Check FIREBASE_SERVICE_ACCOUNT_PATH.",
                    )
                credential = credentials.Certificate(str(path))
                project_id = project_id or credential.project_id
            else:
                credential = credentials.ApplicationDefault()
                project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        except (DefaultCredentialsError, OSError, ValueError) as error:
            raise HTTPException(
                status_code=503,
                detail="Firebase Admin credentials are not configured. Set FIREBASE_SERVICE_ACCOUNT_PATH or configure Google Application Default Credentials.",
            ) from error

        if not project_id:
            raise HTTPException(
                status_code=503,
                detail="Firebase project is not configured. Set FIREBASE_PROJECT_ID.",
            )
        try:
            return firebase_admin.initialize_app(credential, {"projectId": project_id})
        except ValueError as error:
            raise HTTPException(status_code=503, detail="Firebase Admin could not initialize for this project.") from error


def decode_id_token(token: str) -> dict:
    service_account_path = (
        os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    )
    if not service_account_path:
        return _verify_firebase_signature(token)
    if not Path(service_account_path).expanduser().is_file():
        raise HTTPException(
            status_code=503,
            detail="Firebase service-account file was not found. Check FIREBASE_SERVICE_ACCOUNT_PATH.",
        )
    try:
        return firebase_auth.verify_id_token(token, app=_firebase_app(), check_revoked=True)
    except (firebase_auth.InvalidIdTokenError, firebase_auth.ExpiredIdTokenError, firebase_auth.RevokedIdTokenError, firebase_auth.UserDisabledError, ValueError) as error:
        raise HTTPException(
            status_code=401,
            detail="Your Google sign-in token is invalid or expired. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except DefaultCredentialsError as error:
        raise HTTPException(
            status_code=503,
            detail="Firebase Admin credentials are missing. Configure FIREBASE_SERVICE_ACCOUNT_PATH or Google Application Default Credentials.",
        ) from error
    except firebase_auth.CertificateFetchError as error:
        raise HTTPException(status_code=503, detail="Could not verify Firebase signing certificates. Try again shortly.") from error


def revoke_firebase_refresh_tokens(uid: str) -> None:
    service_account_path = (
        os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    )
    if not service_account_path:
        return
    try:
        firebase_auth.revoke_refresh_tokens(uid, app=_firebase_app())
    except (DefaultCredentialsError, ValueError, FirebaseError) as error:
        raise HTTPException(
            status_code=503,
            detail="The current token was blocked, but Firebase could not revoke the account's refresh tokens.",
        ) from error


def _verify_firebase_signature(token: str) -> dict:
    project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    if not project_id:
        raise HTTPException(status_code=503, detail="Firebase project is not configured. Set FIREBASE_PROJECT_ID.")
    try:
        signing_key = _signing_keys.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}",
            options={"require": ["exp", "iat", "aud", "iss", "sub", "auth_time"]},
        )
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(status_code=401, detail="Your Google sign-in token has expired. Sign in again.") from error
    except (jwt.InvalidTokenError, jwt.PyJWKClientError, RequestException) as error:
        raise HTTPException(
            status_code=401,
            detail="Your Google sign-in token could not be verified. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    now = time.time()
    if (
        not isinstance(claims.get("sub"), str)
        or not claims["sub"]
        or claims["iat"] > now
        or claims["auth_time"] > now
    ):
        raise HTTPException(status_code=401, detail="Your Google sign-in token has invalid time or user claims.")
    return claims


def require_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Google sign-in is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_id_token(token.strip())
    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="The verified sign-in token has no user ID.")
    expires_at = claims.get("exp")
    if not isinstance(expires_at, (int, float)):
        raise HTTPException(status_code=401, detail="The verified sign-in token has no expiration.")
    authenticated_at = claims.get("auth_time")
    if not isinstance(authenticated_at, (int, float)):
        raise HTTPException(status_code=401, detail="The verified sign-in token has no authentication time.")
    if is_token_revoked(token.strip()):
        raise HTTPException(
            status_code=401,
            detail="Your sign-in session has been revoked. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = claims.get("email")
    name = claims.get("name")
    picture = claims.get("picture")
    admin_emails = {
        value.strip().lower()
        for value in os.getenv("FIREBASE_ADMIN_EMAILS", "").split(",")
        if value.strip()
    }
    return AuthenticatedUser(
        uid=uid,
        email=email if isinstance(email, str) else None,
        name=name if isinstance(name, str) else None,
        picture=picture if isinstance(picture, str) else None,
        is_admin=(
            isinstance(email, str)
            and claims.get("email_verified") is True
            and email.lower() in admin_emails
        ),
        token_expires_at=int(expires_at),
    )


def require_admin(user: AuthenticatedUser = Depends(require_user)) -> AuthenticatedUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="A configured CampusAnswer administrator account is required to upload policies.")
    return user
