from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext
from uuid import uuid4
from app.core.config import settings
from app.core.logger import log_warning

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = (
    settings.ACCESS_TOKEN_EXPIRE_MINUTES
)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# -----------------------------------
# PASSWORD HASHING
# -----------------------------------
def hash_password(password: str):

    password = password.strip()

    if len(password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=400,
            detail="Password too long (max 72 characters)"
        )

    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 8 characters"
        )

    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str):
    return pwd_context.verify(plain, hashed)

# -----------------------------------
# JWT CREATION
# -----------------------------------

def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
        "jti": str(uuid4())
    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

# -----------------------------------
# JWT DECODING (MISSING IN YOUR CODE)
# -----------------------------------
def decode_access_token(token: str):
    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )

        if "id" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )

        if "role" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )

        return payload

    except JWTError as exc:

        log_warning(

        message="Authentication failed",

        action="TOKEN_INVALID",

        entity="authentication",

        extra={
            "exception":str(exc)
        }

    )

        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication failed"
    )