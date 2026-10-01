from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/hello/{name}")
def hello(name: str, shout: bool = False):
    message = f"Hello, {name}"
    if shout:
        message = message.upper()
    return {"message": message}


@app.get("/items/{item_id}")
def item(item_id: int):
    return {"item": item_id}
