from collections.abc import Mapping
from uuid import uuid4

import httpx

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
RESPONSE_HEADERS_TO_DROP = HOP_BY_HOP_HEADERS | {"content-encoding"}


async def forward_request(
    method: str,
    incoming_headers: Mapping[str, str],
    body: bytes,
    query: str,
    service_url: str,
    path: str,
) -> tuple[int, bytes, dict[str, str]]:
    correlation_id = (
        incoming_headers.get("x-correlation-id")
        or incoming_headers.get("correlation_id")
        or str(uuid4())
    )
    headers = {
        name: value
        for name, value in incoming_headers.items()
        if name.lower() not in HOP_BY_HOP_HEADERS
    }
    headers["X-Correlation-ID"] = correlation_id

    target_url = f"{service_url.rstrip('/')}/{path.lstrip('/')}"
    if query:
        target_url = f"{target_url}?{query}"

    async with httpx.AsyncClient() as client:
        upstream_response = await client.request(
            method,
            target_url,
            headers=headers,
            content=body,
        )

    response_headers = {
        name: value
        for name, value in upstream_response.headers.items()
        if name.lower() not in RESPONSE_HEADERS_TO_DROP
    }
    response_headers["X-Correlation-ID"] = correlation_id
    return upstream_response.status_code, upstream_response.content, response_headers
