from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

COOKIE_NAME = "bms_session"

PUBLIC_PATHS = {"/healthz", "/login", "/api/login", "/favicon.ico"}


def _is_static_asset(path: str) -> bool:
    last = path.rsplit("/", 1)[-1]
    return "." in last


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or _is_static_asset(path)


def extract_token(request: Request) -> Optional[str]:
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie:
        return cookie
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Single shared-token gate.

    Browsers get an HttpOnly cookie after ``POST /api/login``; scripts can use
    ``Authorization: Bearer <token>``. Disabled entirely when ``APP_TOKEN`` is
    empty (localhost / trusted LAN use).
    """

    def __init__(self, app, app_token: str):
        super().__init__(app)
        self.app_token = (app_token or "").strip()

    async def dispatch(self, request: Request, call_next):
        if not self.app_token or _is_public(request.url.path):
            return await call_next(request)

        if extract_token(request) == self.app_token:
            return await call_next(request)

        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return RedirectResponse("/login")
