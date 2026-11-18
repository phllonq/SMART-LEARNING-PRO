import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.core.security import hash_password
from app.core.exceptions import EntityNotFoundException, PermissionDeniedException, DuplicateEntityException, InvalidCredentialsException
from app.modules.auth.models import User, UserRole
from app.modules.auth.router import router as auth_router
from sqlalchemy import select

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("smart_learning")


async def ensure_initial_admin():
    """Ensure that the default system administrator account exists."""
    async with AsyncSessionLocal() as db:
        query = select(User).where(User.email == settings.INITIAL_ADMIN_EMAIL.lower())
        result = await db.execute(query)
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                email=settings.INITIAL_ADMIN_EMAIL.lower(),
                hashed_password=hash_password(settings.INITIAL_ADMIN_PASSWORD),
                full_name=settings.INITIAL_ADMIN_NAME,
                role=UserRole.SUPERADMIN.value,
                is_active=True,
                is_verified=True,
            )
            db.add(admin)
            await db.commit()
            logger.info(f"Default Superadmin created with email: {settings.INITIAL_ADMIN_EMAIL}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup:
    logger.info("Starting SMART LEARNING PRO backend...")
    await init_db()
    await ensure_initial_admin()
    yield
    # Shutdown:
    logger.info("Shutting down SMART LEARNING PRO backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Backend API Modular Monolith cho Nền tảng Học tập Thông minh SMART LEARNING PRO",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Module Routers
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)


# Health Check Endpoint
@app.get("/api/v1/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database": "connected",
        "cache": "active"
    }


# Custom Exception Handlers
@app.exception_handler(EntityNotFoundException)
async def entity_not_found_handler(request: Request, exc: EntityNotFoundException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(PermissionDeniedException)
async def permission_denied_handler(request: Request, exc: PermissionDeniedException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(DuplicateEntityException)
async def duplicate_entity_handler(request: Request, exc: DuplicateEntityException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(InvalidCredentialsException)
async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )
