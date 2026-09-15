from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.exceptions import setup_exception_handlers
from app.core.redis import close_redis_pool, init_redis_pool
from app.core.seed import seed_default_devices
from app.models.base import Base
import app.models.device  # noqa: F401 - Registra modelo no metadata
import app.models.telemetry  # noqa: F401 - Registra modelo no metadata
from app.routers.devices import router as devices_router
from app.routers.websocket import router as websocket_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fleetpulse")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gerenciador de ciclo de vida (startup e shutdown) da aplicação."""
    logger.info("Iniciando %s...", settings.APP_NAME)

    # 1. Inicializa conexões e esquemas
    await init_redis_pool()

    try:
        # Cria as tabelas automaticamente quando o PostgreSQL está disponível.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tabelas do PostgreSQL sincronizadas com sucesso.")

        async with AsyncSessionLocal() as session:
            seeded_count = await seed_default_devices(session)
        logger.info("%d dispositivo(s) padrão disponível(is).", seeded_count)
    except Exception as exc:
        logger.warning(
            "Não foi possível conectar ao banco de dados durante o startup (%s). "
            "A API iniciará, mas certifique-se de que o PostgreSQL/TimescaleDB esteja ativo.",
            exc,
        )

    logger.info("%s pronto para receber conexões.", settings.APP_NAME)
    yield

    # 2. Encerramento gracioso de pools e conexões
    logger.info("Encerrando %s...", settings.APP_NAME)
    await close_redis_pool()
    await engine.dispose()
    logger.info("Recursos liberados com sucesso.")


app = FastAPI(
    title=settings.APP_NAME,
    description="API de telemetria de frota de alta performance construída com FastAPI, PostgreSQL, TimescaleDB e Redis.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração de tratamento customizado de exceções de domínio
setup_exception_handlers(app)

# Registro de routers
app.include_router(devices_router)
app.include_router(websocket_router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Endpoint de verificação de integridade da API."""
    return {"status": "ok", "app": settings.APP_NAME}
