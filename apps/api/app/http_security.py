"""HTTP boundary limits independent of route and domain implementations."""
import asyncio

from starlette.datastructures import Headers
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings


class HttpSecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        limit = 101 * 1024 * 1024 if headers.get("content-type", "").startswith("multipart/form-data") else 2 * 1024 * 1024
        status, detail = None, None
        if headers.get("content-encoding", "identity").lower() != "identity":
            status, detail = 415, "La compresión de solicitudes no está admitida."
        elif scope["method"] in {"POST", "PUT", "PATCH", "DELETE"} and origin and origin not in settings.cors_origins_list:
            status, detail = 403, "Origen no permitido."
        if headers.get("content-length") is not None:
            try:
                length = int(headers["content-length"])
                if length < 0:
                    status, detail = 400, "Tamaño de solicitud no válido."
                elif length > limit:
                    status, detail = 413, "La solicitud supera el tamaño permitido."
            except ValueError:
                status, detail = 400, "Tamaño de solicitud no válido."

        async def secured_send(message):
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                ])
                if scope["path"] not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
                    response_headers.append((b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"))
                if settings.environment == "production":
                    # This host only; do not opt unrelated university subdomains in.
                    response_headers.append((b"strict-transport-security", b"max-age=31536000"))
                message = {**message, "headers": response_headers}
            await send(message)

        if status:
            return await JSONResponse({"message": detail}, status_code=status)(scope, receive, secured_send)
        if settings.environment == "production" and headers.get("content-type", "").startswith("multipart/form-data"):
            # FastAPI parses multipart before route dependencies. Authenticate at
            # this outer boundary so unauthenticated uploads never reach parsing.
            from app.auth import AuthException, verify_session
            from app.dependencies import require_internal_service
            from fastapi.security import HTTPAuthorizationCredentials
            try:
                if scope["path"].startswith("/api/v1/executions/") and scope["path"].endswith("/artifact"):
                    require_internal_service(headers.get("x-internal-token"))
                else:
                    scheme, _, token = headers.get("authorization", "").partition(" ")
                    if scheme.lower() != "bearer" or not token:
                        raise HTTPException(401, "Autenticación requerida antes de cargar archivos.")
                    await run_in_threadpool(verify_session, HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), Request(scope))
            except (HTTPException, AuthException) as exc:
                error_status = exc.status_code if isinstance(exc, HTTPException) else 401
                return await JSONResponse({"message": "Carga no autorizada."}, status_code=error_status)(scope, receive, secured_send)
        received = 0

        async def limited_receive():
            nonlocal received
            try:
                message = await asyncio.wait_for(receive(), timeout=30)
            except TimeoutError:
                raise HTTPException(408, "Se agotó el tiempo para recibir la solicitud.") from None
            received += len(message.get("body", b""))
            if received > limit:
                raise HTTPException(413, "La solicitud supera el tamaño permitido.")
            return message

        await self.app(scope, limited_receive, secured_send)
