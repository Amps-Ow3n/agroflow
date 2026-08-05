from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.core.db import get_db
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token
)
from app.core.logger import (
    log_info,
    log_warning,
    log_error
)
from app.schemas.user_schema import UserRegister
from app.core.exceptions import AgroFlowException
from app.utils.audit import create_audit_log
router = APIRouter(tags=["Auth"])

# ==============================
# REGISTER
# ==============================
@router.post("/register")
def register(payload: UserRegister):
    conn, cursor = get_db()

    if payload.role == "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin cannot self-register"
        )

    try:
        hashed_password = hash_password(payload.password)
        role = payload.role.lower().strip()
        cursor.execute("""
            INSERT INTO users (
                name, email, password, role
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (
            payload.name,
            payload.email,
            hashed_password,
            role
        ))

        user = cursor.fetchone()
        create_audit_log(

    cursor,

    user["id"],

    "REGISTER_USER",

    "user",

    user["id"],

    new_data={
        "role":payload.role,
        "email":payload.email
    }

)
        conn.commit()

        return {
            "message": "User registered successfully",
            "user_id": user["id"]
        }

    except Exception as exc:

        conn.rollback()

        log_error(

        message="Database transaction failed",

        action="REGISTER",

        entity="users",

        exception=exc,

        extra={

            "sql":"INSERT users"

        }

    )

        raise AgroFlowException(

        message="Registration failed",

        status_code=400,

        error_code="REGISTRATION_FAILED"

    )

    finally:
        conn.close()

# ==============================
# LOGIN
# ==============================
@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    conn, cursor = get_db()

    try:
        cursor.execute("""
            SELECT *
            FROM users
            WHERE email = %s
        """, (form_data.username,))

        user = cursor.fetchone()

        if not user:
            log_warning(

        message="Login failed",

        action="LOGIN_FAILED",

        entity="authentication",

        extra={
            "reason":"user_not_found",
            "username":form_data.username
        }

    )
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )

        if not verify_password(
            form_data.password,
            user["password"]
        ):
            log_warning(

    message="Login failed",

    action="LOGIN_FAILED",

    entity="authentication",

    user_id=user["id"],

    extra={
        "reason":"invalid_password"
    }

)
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )

        token = create_access_token({
    "id": user["id"],
    "name": user["name"],
    "role": user["role"]
})
        log_info(

    message="Login successful",

    user_id=user["id"],

    action="LOGIN_SUCCESS",

    entity="authentication",

    extra={
        "role":user["role"]
    }

)
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": user["role"]
        }

    finally:
        conn.close()