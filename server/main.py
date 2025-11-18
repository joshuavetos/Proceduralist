"""FastAPI entrypoint for the Proceduralist deterministic backend.

All middleware and routers are registered here to expose the Tessrax
forensic auditing pipeline over HTTP.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.routers import audit

GOVERNANCE_METADATA = {
    "auditor": "Tessrax Governance Kernel v16",
    "clauses": ["AEP-001", "RVC-001", "EAC-001", "POST-AUDIT-001", "DLK-001", "TESST"],
}

app = FastAPI(title="Proceduralist API", version="1.0.0", openapi_url="/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.governance = GOVERNANCE_METADATA
app.include_router(audit.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
