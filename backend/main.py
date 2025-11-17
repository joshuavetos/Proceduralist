"""FastAPI application entrypoint for Proceduralist backend."""
from __future__ import annotations

from fastapi import FastAPI

from backend import auditor, clauses
from backend.api import analyze as analyze_api
from backend.api import audit as audit_api
from backend.api import compare as compare_api
from backend.api import context as context_api
from backend.api import download as download_api
from backend.api import graph as graph_api
from backend.api import history as history_api
from backend.api import maps as maps_api
from backend.api import queue as queue_api
from backend.api import replay as replay_api
from backend.api import score as score_api
from backend.api import store as store_api
from backend.api import summary as summary_api

app = FastAPI(title="Proceduralist Backend", version="3.0.0")
app.include_router(audit_api.router)
app.include_router(analyze_api.router)
app.include_router(context_api.router)
app.include_router(download_api.router)
app.include_router(graph_api.router)
app.include_router(history_api.router)
app.include_router(maps_api.router)
app.include_router(compare_api.router)
app.include_router(queue_api.router)
app.include_router(replay_api.router)
app.include_router(score_api.router)
app.include_router(summary_api.router)
app.include_router(store_api.router)


auditor_metadata = {"auditor": auditor, "clauses": clauses}
