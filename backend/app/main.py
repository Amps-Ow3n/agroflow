import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import AgroFlowException
from app.core.errors import global_exception_handler
from app.core.logger import log_info,log_warning
from app.core.request_context import set_request_id

from app.routes.auth import router as auth_router
from app.routes.identity import router as identity_router
from app.routes.organizations import router as organizations_router
from app.routes.procurement_routes import router as procurement_router
from app.routes.supplier_registry_routes import router as supplier_registry_router
from app.routes.supplier_evaluation_routes import router as supplier_evaluation_router
from app.routes.supplier_selection_routes import router as supplier_selection_router
from app.routes.purchase_order_routes import router as purchase_order_router
from app.routes.commitment_routes import router as commitment_router
from app.routes.delivery_routes import router as delivery_router
from app.routes.procurement_event_routes import router as procurement_event_router
from app.routes.supplier_performance import router as supplier_performance_router
from app.routes.evidence_routes import router as evidence_router
from app.routes.privacy_routes import router as privacy_router

settings.validate()
app=FastAPI(title="AgroFlow MVP",version="2.1.0")

@app.middleware("http")
async def request_tracking_middleware(request:Request,call_next):
    request_id=str(uuid.uuid4()); set_request_id(request_id); request.state.request_id=request_id
    start=time.time(); log_info(message="REQUEST_START",action="REQUEST_START",entity=request.url.path)
    response=await call_next(request)
    duration=round((time.time()-start)*1000,2)
    log_info(message=f"REQUEST_END duration={duration}ms",action="REQUEST_END",entity=request.url.path)
    response.headers["X-Request-ID"]=request_id
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path not in {"/login", "/register"}:
        session_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)
        if session_cookie:
            import secrets
            csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
            csrf_header = request.headers.get("X-CSRF-Token")
            if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
                return JSONResponse(status_code=403, content={"success": False, "message": "CSRF validation failed.", "error_code": "CSRF_VALIDATION_FAILED"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.ENVIRONMENT == "production":
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.add_exception_handler(Exception,global_exception_handler)

@app.exception_handler(AgroFlowException)
async def agroflow_exception_handler(request:Request,exc:AgroFlowException):
    log_warning(message=exc.message,action="APPLICATION_ERROR",entity=request.url.path)
    return JSONResponse(status_code=exc.status_code,content={"success":False,"message":exc.message,"error_code":exc.error_code})

app.add_middleware(CORSMiddleware,allow_origins=settings.CORS_ORIGINS,allow_credentials=True,allow_methods=["*"],allow_headers=["*", "X-CSRF-Token"])

for router in (
    auth_router,identity_router,organizations_router,procurement_router,
    supplier_registry_router,supplier_evaluation_router,supplier_selection_router,
    purchase_order_router,commitment_router,delivery_router,procurement_event_router,
    supplier_performance_router, evidence_router, privacy_router,
):
    app.include_router(router)

if __name__=="__main__":
    import uvicorn
    uvicorn.run("app.main:app",host="0.0.0.0",port=8000,reload=True)
