from fastapi import FastAPI
from contextlib import asynccontextmanager
from mangum import Mangum
from app.api.v1.api import router
from app.core.config import config
from app.core.logging import logger, logging_middleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import asyncpg
from app.langraph.graph import build_graph



@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application Started")
    try:
        logger.info("Creating Database Pool")
        db_pool = await asyncpg.create_pool(dsn=config.POSTGRES_URI,min_size=2,max_size=10)
        logger.info("Database Pool Created")

    except Exception as e:
        logger.error(f"Error creating Database pool or setting up sessions: {e}")
        raise Exception(f"Error creating Database pool: {e}")
    async with AsyncPostgresSaver.from_conn_string(config.POSTGRES_URI) as checkpointer:
        await checkpointer.setup()
        app.state.db_pool = db_pool
        app.state.graph = await build_graph(checkpointer)
        logger.info("Graph compiled and checkpointer ready")
        yield

    logger.info("Application Shutting Down")
    

app = FastAPI(lifespan=lifespan)
logging_middleware(app)
app.include_router(router,prefix=config.VERSION_PREFIX)
handler = Mangum(app)