from contextlib import asynccontextmanager
from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.api.v1.api import router
from app.core.config import config
from app.core.embed_cors import add_embed_cors
from app.core.logging import logger, logging_middleware
from app.langraph.graph import build_graph
from langgraph_checkpoint_aws import DynamoDBSaver
from app.service.database import Database

connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": None,
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application Started")

    # pool = AsyncConnectionPool(
    #     conninfo=config.POSTGRES_URI,
    #     min_size=1,
    #     max_size=10,
    #     kwargs=connection_kwargs,
    #     open=False,
    # )

    try:
        #logger.info("Opening database connection pool")
        # await pool.open()
        #logger.info("Database connection pool opened")

        # checkpointer = AsyncPostgresSaver(pool)
        # await checkpointer.setup()

        database = Database(
            dialect=config.DIALECT,
            host=config.DATABASE_HOST,
            port=config.DATABASE_PORT,
            user=config.DATABASE_USER,
            password=config.DATABASE_PASSWORD,
            database=config.DATABASE_NAME,
            driver="asyncpg",
        )
        app.state.database = database

        checkpointer = DynamoDBSaver(table_name="langgraph-checkpoints",ttl_seconds=86400 * 7, region_name="ap-south-1",s3_offload_config={"bucket_name": "datalk-langgraph-checkpoints"})
        app.state.checkpointer = checkpointer
        app.state.graph = await build_graph(checkpointer)
        logger.info(f"Graph compiled and checkpointer ready | checkpointer={checkpointer.__class__.__name__!r}")

        yield

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

    finally:
        # await pool.close()
        # logger.info("Database connection pool closed")
        logger.info("Application Shutting Down")


# app = FastAPI(lifespan=lifespan)
app = FastAPI(
    title="Datalk Chat Service",
    description="Datalk Chat Service API Docs",
    version="1.0",
    docs_url='/docs',
    openapi_url='/openapi.json',
    redoc_url=None,
    lifespan=lifespan
)
logging_middleware(app)
add_embed_cors(app)
app.include_router(router, prefix=config.VERSION_PREFIX)

# handler = Mangum(app)