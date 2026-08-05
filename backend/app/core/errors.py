from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.logger import (
    log_error
)

from app.core.request_context import (
    get_request_id
)

def error_response(
    code: str,
    message: str,
    status_code: int,
    details=None
):

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details
            }
        }
    )

async def global_exception_handler(
    request: Request,
    exc: Exception
):

    user_id = "-"


    if hasattr(request.state, "user"):

        user_id = request.state.user.get(
            "id",
            "-"
        )

    log_error(

        message=f"Unhandled exception: {str(exc)}",

        user_id=user_id,

        action="UNEXPECTED_ERROR",

        entity=request.url.path,

        exception=True

    )

    return error_response(

        code="INTERNAL_SERVER_ERROR",

        message="Something went wrong. Please try again later.",

        status_code=500

    )