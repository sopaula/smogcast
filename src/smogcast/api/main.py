from fastapi import FastAPI

from smogcast.api.routes import router


app = FastAPI(
    title="Smogcast API",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(router)
