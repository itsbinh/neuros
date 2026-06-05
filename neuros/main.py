"""FastAPI application entry point for NeurOS."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from neuros.models import ActionInput, NeurOSResponse, QueryInput

logger = logging.getLogger("neuros")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle."""
    logger.info("NeurOS starting up")
    # TODO: initialize DB connections, Qdrant client, Redis connection
    yield
    logger.info("NeurOS shutting down")


app = FastAPI(
    title="NeurOS",
    description="Personal AI operating system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "name": "NeurOS", "version": "0.1.0"}


@app.post("/query", response_model=NeurOSResponse)
async def query(input: QueryInput) -> NeurOSResponse:
    """Process a user query through the agent graph."""
    # TODO: wire up LangGraph pipeline
    raise HTTPException(status_code=501, detail="Agent graph not yet wired")


@app.post("/action", response_model=NeurOSResponse)
async def action(input: ActionInput) -> NeurOSResponse:
    """Invoke a specific skill directly."""
    # TODO: dispatch to skill registry
    raise HTTPException(status_code=501, detail="Skill dispatch not yet wired")
