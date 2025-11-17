"""FastAPI application entrypoint for Proceduralist backend."""
from __future__ import annotations

from fastapi import FastAPI

from backend import auditor, clauses
from backend.api import audit as audit_api
from backend.api import graph as graph_api

app = FastAPI(title="Proceduralist Backend", version="2.0.0")
app.include_router(audit_api.router)
app.include_router(graph_api.router)


auditor_metadata = {"auditor": auditor, "clauses": clauses}
