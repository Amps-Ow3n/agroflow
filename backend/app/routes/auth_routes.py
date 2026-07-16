from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.core.db import get_db
from app.core.auth import hash_password, verify_password, create_access_token
from app.schemas.user_schema import UserRegister

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
        conn.commit()

        return {
            "message": "User registered successfully",
            "user_id": user["id"]
        }

    except Exception as e:
        conn.rollback()
        print("REGISTER ERROR:", e)
        raise HTTPException(
            status_code=400,
            detail=str(e) 
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
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )

        if not verify_password(
            form_data.password,
            user["password"]
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )

        token = create_access_token({
    "id": user["id"],
    "name": user["name"],
    "role": user["role"]
})

        return {
            "access_token": token,
            "token_type": "bearer",
            "role": user["role"]
        }

    finally:
        conn.close()