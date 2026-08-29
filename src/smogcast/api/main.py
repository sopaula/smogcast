from fastapi import FastAPI

from smogcast.api.routes import router


app = FastAPI(
    title="Smogcast API",
    version="0.1.0",
)


app.include_router(router)
