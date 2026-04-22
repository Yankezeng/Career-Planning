from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.api_router import api_router
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.core.seed_runtime_clean import seed_demo_data
from app.core.exceptions import register_exception_handlers
from app.services.job_family_bootstrap_service import JobFamilyBootstrapService
from app.services.persona_image_asset_service import PersonaImageAssetService


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed_demo_data()
    db = SessionLocal()
    try:
        JobFamilyBootstrapService(db).ensure_official_job_family()
        PersonaImageAssetService(db).ensure_cbti_assets()
    finally:
        db.close()
    yield


app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(api_router, prefix=settings.API_V1_STR)
app.mount("/uploads", StaticFiles(directory=str(settings.upload_path)), name="uploads")


@app.get("/")
def root():
    return {"message": f"{settings.PROJECT_NAME} backend is running"}
