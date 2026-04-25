from fastapi import APIRouter

health = APIRouter()


@health.get("/health")
async def status():
    return {"status": "ok"}
