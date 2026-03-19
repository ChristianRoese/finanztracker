import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.database import create_db_and_tables
from backend.routers import import_, transactions, etf, reports
from backend.services.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title="Finanztracker", version="1.0.0", lifespan=lifespan)

origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8080").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(import_.router)
app.include_router(transactions.router)
app.include_router(etf.router)
app.include_router(reports.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Frontend als static files servieren
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
