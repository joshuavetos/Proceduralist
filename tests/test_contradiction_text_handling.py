import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.services.contradictions import _text_from_artifact, detect_conflicts


def test_text_from_artifact_allows_missing_text():
    artifact = {"name": "metadata-only", "type": "file"}
    assert _text_from_artifact(artifact) == ""


def test_detect_conflicts_handles_metadata_only_artifact():
    artifacts = [
        {"name": "upload.pdf", "type": "application/pdf"},
        {"name": "terms", "content": "APR: 5% Member FDIC"},
    ]

    contradictions = detect_conflicts(artifacts)

    assert contradictions == []
