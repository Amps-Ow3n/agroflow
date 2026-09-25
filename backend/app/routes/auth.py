from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from app.core.db import get_db
from app.core.auth import hash_password, verify_password, create_access_token
from app.core.transactions import write_transaction
from app.core.logger import log_warning
from app.core.security import enforce_rate_limit, new_csrf_token
from app.core.config import settings
from app.schemas.user_schema import UserRegister
from app.services.identity_service import get_user_identity

router = APIRouter(tags=["Auth"])


@router.post("/register", status_code=201)
def register(payload: UserRegister, request: Request):
    enforce_rate_limit(request, "register")
    conn, cursor = get_db()
    try:
        with write_transaction(conn):
            cursor.execute("SELECT id FROM users WHERE email = %s", (str(payload.email),))
            if cursor.fetchone():
                raise HTTPException(409, "A user with this email already exists.")
            cursor.execute("SELECT id FROM responsibilities WHERE code = %s", (payload.responsibility,))
            responsibility = cursor.fetchone()
            if not responsibility:
                raise HTTPException(400, "Responsibility does not exist.")
            cursor.execute("""
                INSERT INTO users (name,email,password,status,is_system_admin)
                VALUES (%s,%s,%s,'ACTIVE',FALSE) RETURNING id
            """, (payload.full_name, str(payload.email), hash_password(payload.password)))
            user = cursor.fetchone()
            cursor.execute("""
                INSERT INTO organizations (name,organization_type,status,verification_status)
                VALUES (%s,%s,'PENDING','PENDING') RETURNING id
            """, (payload.organization_name, payload.organization_type))
            organization = cursor.fetchone()
            cursor.execute("""
                INSERT INTO organization_memberships (organization_id,user_id,status)
                VALUES (%s,%s,'PENDING') RETURNING id
            """, (organization["id"], user["id"]))
            membership = cursor.fetchone()
            cursor.execute("INSERT INTO membership_responsibilities (membership_id,responsibility_id) VALUES (%s,%s)", (membership["id"], responsibility["id"]))
            cursor.execute("""
                INSERT INTO organization_verification_records (organization_id,status,verification_type,submitted_by)
                VALUES (%s,'PENDING',%s,%s)
            """, (organization["id"], payload.organization_type, user["id"]))
            if payload.organization_type == "SUPPLIER":
                cursor.execute("INSERT INTO suppliers (organization_id,status) VALUES (%s,'ACTIVE')", (organization["id"],))
            return {"message":"Organization registration submitted for verification.","user_id":user["id"],"organization_id":organization["id"],"verification_status":"PENDING","membership_status":"PENDING"}
    finally:
        conn.close()


@router.post("/login")
def login(response: Response, request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    enforce_rate_limit(request, "login")
    conn, cursor = get_db()
    try:
        cursor.execute("SELECT id,password,status,is_system_admin FROM users WHERE email=%s", (form_data.username,))
        user = cursor.fetchone()
        if not user or not verify_password(form_data.password, user["password"]):
            log_warning(message="Login failed", action="LOGIN_FAILED", entity="authentication")
            raise HTTPException(401, "Invalid credentials")
        if user["status"] != "ACTIVE":
            raise HTTPException(403, "User account is not active.")
        identity = get_user_identity(user["id"])
        if not identity and not user["is_system_admin"]:
            raise HTTPException(403, "User organization identity is not configured.")
        token = create_access_token({"id": user["id"]})
        csrf = new_csrf_token()
        secure = settings.SESSION_COOKIE_SECURE
        response.set_cookie(settings.SESSION_COOKIE_NAME, token, httponly=True, secure=secure, samesite=settings.SESSION_COOKIE_SAMESITE, max_age=settings.SESSION_COOKIE_MAX_AGE, path="/")
        response.set_cookie(settings.CSRF_COOKIE_NAME, csrf, httponly=False, secure=secure, samesite=settings.SESSION_COOKIE_SAMESITE, max_age=settings.SESSION_COOKIE_MAX_AGE, path="/")
        return {"authenticated": True, "token_type": "cookie"}
    finally:
        conn.close()


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/")
    return {"authenticated": False}
