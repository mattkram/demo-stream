from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}
