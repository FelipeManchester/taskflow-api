from fastapi import FastAPI

from app.routers import auth, projects, users

app = FastAPI()

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(users.router)


@app.get("/health")
def health():
    return {"status": "ok"}
