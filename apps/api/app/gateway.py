from fastapi import APIRouter, Depends, HTTPException, Request, Response
from app.auth import verify_access_token

from app.config import settings
from infrastructure.gateway import forward_request

router = APIRouter(tags=["Gateway"], dependencies=[Depends(verify_access_token)])
PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


async def _proxy_request(request: Request, service_url: str, path: str = "") -> Response:
    if settings.internal_service_token is None:
        raise HTTPException(503, "Autenticación interna sin configurar.")
    trusted_headers = {key: value for key, value in request.headers.items() if key.lower() != "x-internal-token"}
    trusted_headers["X-Internal-Token"] = settings.internal_service_token.get_secret_value()
    code, content, headers = await forward_request(
        request.method, trusted_headers, await request.body(), request.url.query, service_url, path
    )
    return Response(content=content, status_code=code, headers=headers)


async def proxy_satellite(request: Request, path: str = "") -> Response:
    return await _proxy_request(request, settings.satellite_service_url, path)


async def proxy_scientific(request: Request, path: str = "") -> Response:
    return await _proxy_request(request, settings.scientific_service_url, path)


router.add_api_route(
    "/api/v1/satellite",
    proxy_satellite,
    methods=PROXY_METHODS,
    name="proxy_satellite_root",
    include_in_schema=False,
)
router.add_api_route(
    "/api/v1/satellite/{path:path}",
    proxy_satellite,
    methods=PROXY_METHODS,
    name="proxy_satellite_path",
    include_in_schema=False,
)
router.add_api_route(
    "/api/v1/scientific",
    proxy_scientific,
    methods=PROXY_METHODS,
    name="proxy_scientific_root",
    include_in_schema=False,
)
router.add_api_route(
    "/api/v1/scientific/{path:path}",
    proxy_scientific,
    methods=PROXY_METHODS,
    name="proxy_scientific_path",
    include_in_schema=False,
)
