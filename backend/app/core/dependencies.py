from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.auth import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# -----------------------------------
# BASE USER (AUTHENTICATION ONLY)
# -----------------------------------
def require_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    return payload

# -----------------------------------
# ROLE CHECK HELPERS
# -----------------------------------
def require_role(allowed_roles: list):
    def wrapper(user=Depends(require_user)):
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires: {allowed_roles}"
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