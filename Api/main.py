
from fastapi import FastAPI
import uvicorn

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "API de ejemplo con datos locales"}


@app.get("/test")
def read_root():
    return {"message": "API de ejemplo con datos locales"}


@app.get("/version")
def get_version():
    return {"version": __version__}


@app.get("/health", summary="Liveness probe")
async def health():
    return {"status": "ok"}

