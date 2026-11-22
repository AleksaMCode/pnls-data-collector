import asyncio
import logging
import os
from contextlib import asynccontextmanager
from itertools import cycle
from typing import Iterator

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from middleware import FirebaseAuthMiddleware, setup_firebase_auth
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from settings import (
    HEALTH_CHECK_INTERVAL_SECONDS,
    IS_PROD,
    PROXY_RATE_LIMIT,
    RATE_LIMIT_STORAGE_URI,
    SERVICE_DESCRIPTION,
    SERVICE_NAME,
    SERVICE_VERSION,
    UPSTREAM_TIMEOUT_SECONDS,
)
from starlette.middleware.cors import CORSMiddleware

load_dotenv()
logger = logging.getLogger(__name__)

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
}

upstream_cycle: Iterator[str] | None = None
upstream_urls: list[str] = []


async def health_check() -> None:
    while True:
        try:
            async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS) as client:
                for upstream_url in upstream_urls:
                    health_url = f"{upstream_url}/health"
                    try:
                        response = await client.get(health_url)
                        if response.status_code >= 400:
                            logger.warning(
                                "Upstream health check failed for %s with status %s",
                                health_url,
                                response.status_code,
                            )
                    except httpx.RequestError as exc:
                        logger.warning("Upstream health check error for %s: %s", health_url, exc)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            break


def _health_rate_limit_key(request: Request) -> str:
    client_host = request.client.host if request.client else "unknown"
    return client_host


def _proxy_rate_limit_key(request: Request) -> str:
    user_id = getattr(request.state, "firebase_user_id", None)
    if not user_id:
        return "anonymous"
    return str(user_id)


def _parse_upstream_urls() -> list[str]:
    raw_urls = os.getenv("STATS_API_URLS", "")
    urls = [url.strip().rstrip("/") for url in raw_urls.split(",") if url.strip()]
    if not urls:
        raise RuntimeError("STATS_API_URLS must contain at least one API URL.")
    return urls


def _next_upstream_base_url() -> str:
    if upstream_cycle is None:
        raise RuntimeError("Upstream URLs are not initialized.")
    return next(upstream_cycle)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global upstream_cycle, upstream_urls
    setup_firebase_auth()
    upstream_urls = _parse_upstream_urls()
    upstream_cycle = cycle(upstream_urls)
    health_check_task = asyncio.create_task(health_check())
    yield
    health_check_task.cancel()
    try:
        await health_check_task
    except asyncio.CancelledError:
        pass


limiter = Limiter(
    key_func=_proxy_rate_limit_key,
    storage_uri=RATE_LIMIT_STORAGE_URI,
)

app = FastAPI(
    lifespan=lifespan,
    title=SERVICE_NAME,
    description=SERVICE_DESCRIPTION,
    version=SERVICE_VERSION,
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    openapi_url=None if IS_PROD else "/openapi.json",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if IS_PROD:
    origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    app.add_middleware(FirebaseAuthMiddleware)
else:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
@limiter.limit("1000/hour", key_func=_health_rate_limit_key)
async def health(request: Request) -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
@limiter.limit(PROXY_RATE_LIMIT, key_func=_proxy_rate_limit_key)
async def proxy_request(path: str, request: Request) -> Response:
    target_base_url = _next_upstream_base_url()
    target_url = f"{target_base_url}/{path}" if path else f"{target_base_url}/"

    user_id = getattr(request.state, "firebase_user_id", None)
    forwarded_headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }
    if user_id:
        forwarded_headers["X-User-Id"] = str(user_id)

    try:
        async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS) as client:
            upstream_response = await client.request(
                method=request.method,
                url=target_url,
                params=request.query_params,
                headers=forwarded_headers,
                content=await request.body(),
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach upstream Stats API: {exc}",
        ) from exc

    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SERVER_URL", "0.0.0.0"),
        port=int(os.getenv("SERVER_PORT", "9099")),
        reload=False,
    )
