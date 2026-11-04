from fastapi import FastAPI
from hr_minds.settings.config import settings

app = FastAPI()


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} in Debug mode: {settings.DEBUG}"}