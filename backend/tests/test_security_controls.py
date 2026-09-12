import os
import sys
from pathlib import Path

# Allow tests to import the backend package when executed from repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import InMemoryRateLimiter


def test_rate_limiter_blocks_after_limit():
    limiter = InMemoryRateLimiter()
    assert limiter.allow("x", 2, 60) is True
    assert limiter.allow("x", 2, 60) is True
    assert limiter.allow("x", 2, 60) is False


def test_rate_limiter_scopes_keys():
    limiter = InMemoryRateLimiter()
    assert limiter.allow("a", 1, 60) is True
    assert limiter.allow("b", 1, 60) is True


def test_auth_token_prefers_authorization_header():
    from app.core.security import get_auth_token

    class RequestStub:
        cookies = {"agroflow_access_token": "cookie-token"}

    assert get_auth_token(RequestStub(), "header-token") == "header-token"


def test_auth_token_falls_back_to_session_cookie():
    from app.core.security import get_auth_token

    class RequestStub:
        cookies = {"agroflow_access_token": "cookie-token"}

    assert get_auth_token(RequestStub(), None) == "cookie-token"


def test_evidence_file_validation_rejects_extension_mismatch():
    from io import BytesIO
    from fastapi import UploadFile, HTTPException
    from starlette.datastructures import Headers
    from app.services.evidence_document_service import validate_file

    file = UploadFile(filename="document.exe", file=BytesIO(b"%PDF-1.7"), headers=Headers({"content-type": "application/pdf"}))

    try:
        validate_file(file)
        assert False, "Expected extension validation failure"
    except HTTPException as exc:
        assert exc.status_code == 400


def test_evidence_file_validation_rejects_fake_mime_content():
    from io import BytesIO
    from fastapi import UploadFile, HTTPException
    from starlette.datastructures import Headers
    from app.services.evidence_document_service import validate_file

    file = UploadFile(filename="document.pdf", file=BytesIO(b"not a pdf"), headers=Headers({"content-type": "application/pdf"}))

    try:
        validate_file(file)
        assert False, "Expected content signature validation failure"
    except HTTPException as exc:
        assert exc.status_code == 400


def test_evidence_file_validation_accepts_matching_pdf():
    from io import BytesIO
    from fastapi import UploadFile
    from starlette.datastructures import Headers
    from app.services.evidence_document_service import validate_file

    file = UploadFile(filename="document.pdf", file=BytesIO(b"%PDF-1.7"), headers=Headers({"content-type": "application/pdf"}))

    validate_file(file)
