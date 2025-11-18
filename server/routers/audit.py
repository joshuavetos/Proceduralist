"""Audit router for exposing Tessrax deterministic analyses over HTTP."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from server.services import engine
from server.services.pdf_generator import ForensicReportPDF

router = APIRouter(prefix="/api", tags=["audit"])
GOVERNANCE_METADATA = engine.GOVERNANCE_METADATA


class SummaryStats(BaseModel):
    """Structural summary of the ingested artifacts."""

    model_config = ConfigDict(frozen=True)

    artifact_count: int
    file_count: int
    text_present: bool
    url_present: bool
    merkle_root: str


class Contradiction(BaseModel):
    """Representation of a deterministic contradiction finding."""

    model_config = ConfigDict(frozen=True)

    location: str
    description: str
    severity: str


class AuditReport(BaseModel):
    """API response conveying the full audit result."""

    model_config = ConfigDict(frozen=True)

    summary: SummaryStats
    contradictions: list[Contradiction]
    governance: dict


async def _validate_inputs(files: List[UploadFile], text: str | None, url: str | None) -> None:
    """Enforce strict input requirements for AEP-001 compliance."""

    if not files and not (text and text.strip()) and not (url and url.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of files, text, or url must be provided for auditing.",
        )


@router.post("/audit", response_model=AuditReport, status_code=status.HTTP_200_OK)
async def run_audit(
    files: List[UploadFile] = File(default_factory=list),
    text: str | None = Form(default=None),
    url: str | None = Form(default=None),
) -> AuditReport:
    """Run the deterministic Tessrax audit core on supplied inputs."""

    await _validate_inputs(files, text, url)

    artifacts = await engine.ingest_data(files=files, text=text, url=url)
    merkle_root = engine.run_deterministic_core(artifacts)
    contradictions = engine.detect_contradictions(artifacts)

    counts = engine.count_artifacts(artifacts)
    summary = SummaryStats(
        artifact_count=len(artifacts),
        file_count=counts["file"],
        text_present=counts["text"] > 0,
        url_present=counts["url"] > 0,
        merkle_root=merkle_root,
    )

    return AuditReport(
        summary=summary,
        contradictions=[Contradiction(**item) for item in contradictions],
        governance=GOVERNANCE_METADATA,
    )


@router.post("/audit/pdf", response_class=StreamingResponse, status_code=status.HTTP_200_OK)
async def generate_audit_pdf(report: dict = Body(..., embed=False)) -> StreamingResponse:
    """Generate a deterministic PDF for a supplied audit report."""

    if not isinstance(report, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audit PDF generation requires a JSON object payload.",
        )

    summary_section = report.get("summary")
    if not isinstance(summary_section, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audit PDF summary section is missing or malformed.",
        )

    merkle_root = summary_section.get("merkle_root")
    if not merkle_root:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Summary must include a merkle_root for ledger anchoring.",
        )

    generator = ForensicReportPDF(ledger_id=str(merkle_root))
    pdf_bytes = generator.generate(report)

    return StreamingResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=audit-report.pdf"},
    )
