from fastapi import FastAPI
from contextlib import asynccontextmanager
from .configs.config import settings
from .database.database import engine, Base
from .routes.parser_routes import parser_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP CODE ---
    # Load your ML model, connect to a database, etc.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # --- SHUTDOWN CODE ---
    # Clean up resources, close connections, etc.
    


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)



parser_prefix = settings.PARSER_PREFIX

# register here routes
app.include_router(parser_router, prefix=parser_prefix)
