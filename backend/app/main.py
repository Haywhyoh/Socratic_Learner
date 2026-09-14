from fastapi import FastAPI

from app.api.v1 import api_router

app = FastAPI(title="Socratic Learner", version="0.1.0")
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
