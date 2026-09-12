from pathlib import Path
from fastapi import HTTPException
from app.core.config import settings


def safe_evidence_path(storage_reference: str) -> Path:
    if not storage_reference or Path(storage_reference).is_absolute():
        raise HTTPException(500, "Evidence storage reference is invalid.")
    root = Path(settings.EVIDENCE_STORAGE_DIR).resolve()
    candidate = (root / storage_reference).resolve()
    if root not in candidate.parents:
        raise HTTPException(500, "Evidence storage reference is invalid.")
    return candidate
