from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.firebase_app import init_firebase

_bearer = HTTPBearer(auto_error=False)

# Email/password operators only; Google OAuth users are end-users.
_ADMIN_SIGN_IN_PROVIDER = "password"


def _verify_id_token(credentials: HTTPAuthorizationCredentials) -> dict[str, Any]:
    if not init_firebase():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth unavailable")

    try:
        from firebase_admin import auth

        return auth.verify_id_token(credentials.credentials)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token") from exc


def _sign_in_provider(decoded: dict[str, Any]) -> str | None:
    firebase = decoded.get("firebase")
    if not isinstance(firebase, dict):
        return None
    provider = firebase.get("sign_in_provider")
    return provider if isinstance(provider, str) else None


def _admin_email_allowlist() -> set[str]:
    raw = settings.admin_emails or ""
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _is_allowlisted_admin_email(decoded: dict[str, Any]) -> bool:
    allowlist = _admin_email_allowlist()
    if not allowlist:
        return False
    email = decoded.get("email")
    if not isinstance(email, str) or not email.strip():
        return False
    return email.strip().lower() in allowlist


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any] | None:
    """Return decoded Firebase ID token if a Bearer token is present; else None.

    Invalid tokens raise 401. Missing credentials are allowed (anonymous).
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    return _verify_id_token(credentials)


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """Authorize operators: password-provider users whose email is in ADMIN_EMAILS.

    Google OAuth users are regular end-users and cannot access admin APIs.
    Keep Email/Password enabled for operator sign-in; restrict who is admin via ADMIN_EMAILS.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")

    decoded = _verify_id_token(credentials)
    if _sign_in_provider(decoded) != _ADMIN_SIGN_IN_PROVIDER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    if not _is_allowlisted_admin_email(decoded):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return decoded
