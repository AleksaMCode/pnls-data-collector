import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from core.redis.helpers import init_redis_cache
from middleware import FirebaseAuthMiddleware, setup_firebase_auth
from routers import stats_router
from settings import SERVICE_DESCRIPTION, SERVICE_NAME, SERVICE_VERSION
from dotenv import load_dotenv

from util.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = await init_redis_cache()
    setup_firebase_auth()
    logger.info("Server starting.")
    yield
    await redis_client.aclose()
    logger.info("Server shutting down.")

ENV = os.getenv("SERVER_ENV", "dev")
IS_PROD = ENV == "production"

app = FastAPI(
    lifespan=lifespan,
    title=SERVICE_NAME,
    description=SERVICE_DESCRIPTION,
    version=SERVICE_VERSION,
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    openapi_url=None if IS_PROD else "/openapi.json",
)

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
app.include_router(stats_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SERVER_URL", "0.0.0.0"),
        port=int(os.getenv("SERVER_PORT", "9098")),
        reload=False,
    )
