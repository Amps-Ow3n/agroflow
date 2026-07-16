from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from app.routes.auth_routes import router as auth_router
from app.routes.source_routes import router as source_router
from app.routes.commitment_routes import router as commitment_router
from app.routes.chain_routes import router as chain_router
from app.routes.matching_routes import router as matching_router
from app.routes.delivery_routes import router as delivery_router

from app.routes.supplier_dashboard_routes import router as supplier_dashboard_router
from app.routes.school_dashboard_routes import router as school_dashboard_router
from app.routes.system_dashboard_routes import router as system_dashboard_router
from app.routes.school_routes import router as school_router
from app.routes.demand_routes import router as demand_router
from app.routes.intelligence_routes import router as intelligence_router
from app.routes import admin_delivery_routes

# ======================================================
# LOAD ENVIRONMENT
# ======================================================
load_dotenv()

# ======================================================
# APP INIT
# ======================================================
app = FastAPI(
    title="AgroFlow MVP",
    version="2.0.0"
)

# ======================================================
# CORS
# ======================================================
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

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
app.include_router(matching_router)
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