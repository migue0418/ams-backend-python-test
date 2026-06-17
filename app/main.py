from contextlib import asynccontextmanager

from api.routes import router as api_router
from domain.repository import get_repository
from fastapi import FastAPI
from services import pipeline, provider_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    await provider_client.start()
    await pipeline.start(get_repository())

    yield

    await pipeline.stop()
    await provider_client.stop()


app = FastAPI(title="Notification Service (Technical Test)", lifespan=lifespan)

app.include_router(api_router, prefix="/v1")
