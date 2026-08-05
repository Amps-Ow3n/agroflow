from fastapi import (
    FastAPI,
    Request
)
import uuid
import time

from app.core.request_context import (
    set_request_id
)
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routes.auth_routes import router as auth_router
from app.routes.source_routes import router as source_router
from app.routes.commitment_routes import router as commitment_router
from app.routes.chain_routes import router as chain_router
from app.routes.delivery_routes import router as delivery_router

from app.routes.supplier_dashboard_routes import router as supplier_dashboard_router
from app.routes.school_dashboard_routes import router as school_dashboard_router
from app.routes.system_dashboard_routes import router as system_dashboard_router
from app.routes.school_routes import router as school_router
from app.routes.demand_routes import router as demand_router
from app.routes.intelligence_routes import router as intelligence_router
from app.routes import admin_delivery_routes
from app.routes.audit_routes import router as audit_router
from app.core.errors import global_exception_handler
from app.core.logger import (
    log_warning,
    log_info,
    log_error
)
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AgroFlowException

# ======================================================
# APP INIT
# ======================================================
app = FastAPI(
    title="AgroFlow MVP",
    version="2.0.0"
)

@app.middleware("http")
async def request_tracking_middleware(
    request: Request,
    call_next
):

    request_id = str(
        uuid.uuid4()
    )

    set_request_id(
        request_id
    )

    request.state.request_id = (
        request_id
    )

    start_time = time.time()


    log_info(
        message="REQUEST_START",
        action="REQUEST_START",
        entity=request.url.path
    )


    response = await call_next(
        request
    )


    duration = round(
        (time.time() - start_time) * 1000,
        2
    )


    log_info(
        message=f"REQUEST_END duration={duration}ms",
        action="REQUEST_END",
        entity=request.url.path
    )


    response.headers[
        "X-Request-ID"
    ] = request_id


    return response

app.add_exception_handler(
    Exception,
    global_exception_handler
)

@app.exception_handler(AgroFlowException)
async def agroflow_exception_handler(
    request: Request,
    exc: AgroFlowException
):

    log_warning(
    message=exc.message,
    action="APPLICATION_ERROR",
    entity=request.url.path
)

    return JSONResponse(

        status_code=exc.status_code,

        content={

            "success":False,

            "message":exc.message,

            "error_code":exc.error_code

        }

    )
# ======================================================
# CORS
# ======================================================
origins = settings.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ======================================================
# REGISTER ROUTES
# ======================================================
app.include_router(auth_router)
app.include_router(source_router)
app.include_router(commitment_router)
app.include_router(chain_router)
app.include_router(delivery_router)

app.include_router(supplier_dashboard_router)
app.include_router(school_dashboard_router)
app.include_router(system_dashboard_router)
app.include_router(intelligence_router)
app.include_router(school_router)
app.include_router(demand_router)
app.include_router(
    admin_delivery_routes.router
)
app.include_router(
    audit_router
)
# ======================================================
# ENTRYPOINT
# ======================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )