from fastapi import FastAPI
from fastapi.responses import PlainTextResponse


app = FastAPI(title="DMHY Tool", version="0.1.0")


@app.get("/", response_class=PlainTextResponse)
async def home() -> str:
    return "DMHY Tool OK"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "dmhytool"}
