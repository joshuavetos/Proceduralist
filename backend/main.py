"""FastAPI application entrypoint for Proceduralist backend."""
from __future__ import annotations

from fastapi import FastAPI

from backend import auditor, clauses
from backend.api import audit as audit_api
from backend.api import context as context_api
from backend.api import download as download_api
from backend.api import graph as graph_api
from backend.api import maps as maps_api
from backend.api import replay as replay_api
from backend.api import score as score_api
from backend.api import store as store_api

app = FastAPI(title="Proceduralist Backend", version="2.0.0")
app.include_router(audit_api.router)
app.include_router(context_api.router)
app.include_router(download_api.router)
app.include_router(graph_api.router)
app.include_router(maps_api.router)
app.include_router(replay_api.router)
app.include_router(score_api.router)
app.include_router(store_api.router)


auditor_metadata = {"auditor": auditor, "clauses": clauses}
