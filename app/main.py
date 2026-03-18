from contextlib import asynccontextmanager
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

from .database import engine, Base, SessionLocal
from .routes import automations, conversations, webhooks, companies, analytics
from .routes import accounts, multipost, analytics_posts, batch_posts
from .services.scheduler import start_scheduler, stop_scheduler

# Criar tabelas (existentes + novas do multipost)
Base.metadata.create_all(bind=engine)

# ── Logging Estruturado ────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ── Rate Limiter ───────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: inicia o scheduler de posts agendados
    logger.info("🚀 Iniciando scheduler de posts agendados...")
    start_scheduler(SessionLocal)
    yield
    # Shutdown: para o scheduler limpo
    logger.info("🛑 Parando scheduler...")
    stop_scheduler()


app = FastAPI(
    title="Fazza Automation API",
    description="Automação de DMs, comentários e multipost para Instagram.",
    version="3.0.0",
    lifespan=lifespan,
)

# Aplicar rate limiter
app.state.limiter = limiter
app.add_exception_handler(Exception, lambda request, exc: {"error": str(exc)})

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)


@app.get("/health")
def health():
    return {"status": "healthy", "version": "3.0.0"}


# ── Rotas existentes ──────────────────────────────
app.include_router(automations.router, prefix="/api/automations", tags=["Automations"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["Conversations"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])

# ── Rotas Multipost (NOVAS) ───────────────────────
app.include_router(accounts.router, prefix="/api/accounts", tags=["Instagram Accounts"])
app.include_router(multipost.router, prefix="/api/posts", tags=["Multipost"])
app.include_router(analytics_posts.router, prefix="/api/analytics/posts", tags=["Post Analytics"])
app.include_router(batch_posts.router, prefix="/api/posts", tags=["Batch Posts"])
