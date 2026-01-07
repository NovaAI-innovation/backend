"""
FastAPI application entry point.
Main application instance with middleware and route configuration.
"""
from fastapi import FastAPI, Request, status, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging
import asyncio

from app.config import settings
from app.database import get_db, init_db, close_db
from app.services.cloudinary_service import validate_cloudinary_config
from app.routes import gallery, cms

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI application instance
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
)

# CORS Middleware Configuration
# Allow ALL origins for now to fix CORS issues
# In production, you should restrict this to specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Must be False when using wildcard origin
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],  # Allow all headers including X-CMS-Password
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Note: Custom CORS middleware removed as CORSMiddleware with allow_origins=["*"] handles all cases


# Request logging middleware for debugging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming requests for debugging, especially OPTIONS requests."""
    method = request.method
    path = request.url.path
    origin = request.headers.get("origin", "No origin header")
    access_control_request_method = request.headers.get("access-control-request-method", "N/A")
    access_control_request_headers = request.headers.get("access-control-request-headers", "N/A")
    
    # Detailed logging for OPTIONS requests (CORS preflight)
    if method == "OPTIONS":
        logger.info(
            f"OPTIONS preflight request to {path}\n"
            f"  Origin: {origin}\n"
            f"  Access-Control-Request-Method: {access_control_request_method}\n"
            f"  Access-Control-Request-Headers: {access_control_request_headers}\n"
            f"  All headers: {dict(request.headers)}"
        )
    else:
        logger.debug(f"Incoming {method} request to {path} from origin: {origin}")
    
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code} for {method} {path}")
        
        # Log CORS headers in response for OPTIONS
        if method == "OPTIONS":
            cors_headers = {
                k: v for k, v in response.headers.items() 
                if k.lower().startswith("access-control")
            }
            logger.info(f"CORS response headers: {cors_headers}")
        
        return response
    except Exception as e:
        logger.error(
            f"Error processing {method} {path}: {str(e)}\n"
            f"  Origin: {origin}\n"
            f"  Error type: {type(e).__name__}",
            exc_info=True
        )
        raise

# Note: Explicit OPTIONS handlers removed - CORSMiddleware handles all preflight requests automatically


# Include routers (after OPTIONS handlers)
app.include_router(gallery.router, prefix="/api", tags=["gallery"])
app.include_router(cms.router, prefix="/api", tags=["CMS"])


def add_cors_headers(response: JSONResponse, request: Request) -> JSONResponse:
    """
    Add CORS headers to error responses.
    Since we use allow_origins=["*"], we set Access-Control-Allow-Origin to "*" for all responses.

    Args:
        response: The JSONResponse to add headers to
        request: The incoming request

    Returns:
        JSONResponse with CORS headers added
    """
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Expose-Headers"] = "*"

    return response


# Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions (401, 403, 404, etc.) with CORS headers."""
    logger.error(
        f"HTTPException on {request.method} {request.url.path}:\n"
        f"  Status: {exc.status_code}\n"
        f"  Origin: {request.headers.get('origin', 'No origin')}\n"
        f"  Detail: {exc.detail}"
    )
    
    # Handle both string and dict detail formats
    if isinstance(exc.detail, dict):
        content = exc.detail
    else:
        content = {"error": exc.detail, "detail": str(exc.detail)}
    
    response = JSONResponse(
        status_code=exc.status_code,
        content=content
    )
    
    return add_cors_headers(response, request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    """Handle request validation errors."""
    logger.error(
        f"Validation error on {request.method} {request.url.path}:\n"
        f"  Origin: {request.headers.get('origin', 'No origin')}\n"
        f"  Headers: {dict(request.headers)}\n"
        f"  Errors: {exc.errors()}"
    )
    response = JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Validation error",
            "detail": exc.errors()
        }
    )
    return add_cors_headers(response, request)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}:\n"
        f"  Origin: {request.headers.get('origin', 'No origin')}\n"
        f"  Error: {str(exc)}\n"
        f"  Error type: {type(exc).__name__}",
        exc_info=True
    )
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred"
        }
    )
    return add_cors_headers(response, request)


# Root Endpoints
@app.get("/")
async def root():
    """Root endpoint - API health check."""
    return {
        "message": settings.API_TITLE,
        "status": "healthy",
        "version": settings.API_VERSION
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/health/db")
async def health_check_db(db: AsyncSession = Depends(get_db)):
    """
    Database health check endpoint.
    Tests database connection and returns status.
    """
    try:
        result = await db.execute(text("SELECT 1"))
        return {
            "database": "connected",
            "status": "healthy",
            "result": result.scalar()
        }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}", exc_info=True)
        return {
            "database": "error",
            "status": "unhealthy",
            "error": "Database connection failed"
        }


@app.get("/health/cloudinary")
async def health_check_cloudinary():
    """
    Cloudinary health check endpoint.
    Validates Cloudinary configuration.
    """
    try:
        is_configured = validate_cloudinary_config()
        if is_configured:
            return {
                "cloudinary": "configured",
                "status": "healthy",
                "cloud_name": settings.CLOUDINARY_CLOUD_NAME
            }
        else:
            return {
                "cloudinary": "not_configured",
                "status": "warning",
                "message": "Cloudinary credentials not set in environment variables"
            }
    except Exception as e:
        logger.error(f"Cloudinary health check failed: {str(e)}", exc_info=True)
        return {
            "cloudinary": "error",
            "status": "unhealthy",
            "error": str(e)
        }


@app.on_event("startup")
async def startup_event():
    """
    Initialize database connection on application startup.
    Non-blocking: app will start even if database connection fails.
    """
    logger.info(f"CORS allowed origins: {settings.CORS_ORIGINS}")
    
    if settings.DATABASE_URL:
        try:
            await init_db()
            logger.info("Database connection established successfully")
        except Exception as e:
            logger.error(
                f"Failed to initialize database on startup: {str(e)}\n"
                f"The application will continue to run, but database-dependent endpoints will fail.\n"
                f"Please check your DATABASE_URL configuration and network connectivity."
            )
            # Don't raise - allow app to start without database for non-db endpoints
    else:
        logger.info("DATABASE_URL not configured - database features will be unavailable")


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on application shutdown."""
    if settings.DATABASE_URL:
        try:
            await close_db()
        except Exception as e:
            # Ignore cancellation errors during shutdown - they're expected
            if not isinstance(e, (KeyboardInterrupt, asyncio.CancelledError)):
                logger.warning(f"Error during database shutdown: {str(e)}")

