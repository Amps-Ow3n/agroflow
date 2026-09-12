from fastapi import APIRouter, Depends
from app.core.config import settings
from app.core.dependencies import require_user

router = APIRouter(tags=["Privacy"])


@router.get("/privacy/notice")
def privacy_notice():
    return {
        "version": settings.PRIVACY_POLICY_VERSION,
        "contact": settings.PRIVACY_CONTACT_EMAIL,
        "status": "engineering privacy notice",
        "legal_status": "This notice does not certify legal compliance.",
        "purposes": ["identity and access management", "school procurement traceability", "supplier evaluation", "audit and accountability", "security and service operation"],
        "security_controls": ["organization-scoped authorization", "password hashing", "secure session cookies", "CSRF protection", "controlled evidence access", "input validation", "audit logging", "rate limiting"],
        "rights": ["access", "correction", "lawful processing enquiries", "complaints through applicable channels"],
    }


@router.get("/privacy/me")
def privacy_me(user=Depends(require_user)):
    return {
        "user": user.get("user"),
        "memberships": user.get("memberships", []),
        "purpose": "Access to personal identity and organization-membership information held in the authenticated session context.",
    }
