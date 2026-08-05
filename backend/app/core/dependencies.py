from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.auth import decode_access_token
from app.core.logger import log_warning

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# -----------------------------------
# BASE USER (AUTHENTICATION ONLY)
# -----------------------------------
def require_user(token: str = Depends(oauth2_scheme)):

    payload = decode_access_token(token)

    if not payload.get("id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

    return payload
# -----------------------------------
# ROLE CHECK HELPERS
# -----------------------------------
def require_role(allowed_roles: list):
    def wrapper(user=Depends(require_user)):

        role = user.get("role")

        if role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )

        if role not in allowed_roles:
            log_warning(

        message="Permission denied",

        user_id=user["id"],

        action="PERMISSION_DENIED",

        entity="authorization",

        extra={
            "role":role,
            "allowed_roles":allowed_roles
        }

    )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action."
            )

        return user

    return wrapper
# -----------------------------------
# SPECIFIC ROLES (CLEAN + SCALABLE)
# -----------------------------------

require_admin = require_role(["admin"])

require_buyer = require_role(["buyer", "school", "admin"])

require_supplier = require_role([
    "farmer",
    "trader",
    "cooperative",
    "processor",
    "supplier"
])

require_source_actor = require_role([
    "supplier"
])

require_farmer = require_role(["farmer"])