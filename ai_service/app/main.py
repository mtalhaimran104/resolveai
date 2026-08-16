from app.api.routers.priority_prediction import router as priority_router
from fastapi import FastAPI

from app.api.routers.classification import router as classification_router


app = FastAPI()
app.include_router(priority_router)

@app.get("/hello")
def hello():
    return {"message": "Hello World"}


app.include_router(classification_router)