"""
FastAPI application entry point.
Main application instance with middleware and route configuration.
"""
from fastapi import FastAPI, Request, status, Depends
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
# Allow requests from GitHub Pages frontend and local development
# Note: For file:// protocol, browsers send "null" as origin
# We allow null origin for development (file:// protocol)
# In production, credentials should be enabled and null origin should be blocked
cors_origins = list(settings.CORS_ORIGINS) if settings.CORS_ORIGINS else []
# Allow null origin for file:// protocol in development
cors_origins.append("null")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,  # Set to False when allowing null origin (CORS spec requirement)
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Custom CORS middleware to ensure headers are set for all allowed origins
@app.middleware("http")
async def cors_ensure_headers_middleware(request: Request, call_next):
    """
    Custom middleware to ensure CORS headers are set for all allowed origins.
    This acts as a fallback if CORSMiddleware doesn't set headers properly.
    """
    origin = request.headers.get("origin")
    
    # Process the request
    response = await call_next(request)
    
    # Check if origin is in allowed list or is null
    if origin:
        is_allowed_origin = (
            origin in cors_origins or 
            origin == "null" or
            any(origin.startswith(allowed.replace("*", "")) for allowed in cors_origins if "*" in allowed)
        )
        
        if is_allowed_origin:
            # Check if Access-Control-Allow-Origin is already set (case-insensitive)
            has_cors_header = any(
                key.lower() == "access-control-allow-origin" 
                for key in response.headers.keys()
            )
            
            if not has_cors_header:
                # Set CORS headers
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
                response.headers["Access-Control-Allow-Headers"] = "*"
                response.headers["Access-Control-Expose-Headers"] = "*"
                logger.info(f"Added CORS headers for origin '{origin}' to {request.method} {request.url.path}")
            else:
                # Ensure the header value matches the origin
                for key, value in list(response.headers.items()):
                    if key.lower() == "access-control-allow-origin":
                        if value != origin and origin != "null":
                            response.headers[key] = origin
                            logger.info(f"Updated CORS header to '{origin}' for {request.method} {request.url.path}")
                        break
    
    return response


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

# Include routers
app.include_router(gallery.router, prefix="/api", tags=["gallery"])
app.include_router(cms.router, prefix="/api", tags=["CMS"])

# Exception Handlers
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
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Validation error",
            "detail": exc.errors()
        }
    )


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
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred"
        }
    )


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


@app.options("/api/gallery-images")
async def options_gallery_images(request: Request):
    """
    Explicit OPTIONS handler for gallery-images endpoint.
    Handles null origin (file:// protocol) for development.
    """
    origin = request.headers.get("origin", "No origin")
    logger.info(
        f"Explicit OPTIONS handler called for /api/gallery-images\n"
        f"  Origin: {origin}\n"
        f"  All headers: {dict(request.headers)}"
    )
    
    # Handle null origin (file:// protocol)
    # When origin is null, we can't use credentials (CORS spec)
    allow_origin = origin if origin != "No origin" else "*"
    if origin == "null":
        allow_origin = "null"
    
    # Return empty response with CORS headers
    return JSONResponse(
        content={},
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
        }
    )


@app.options("/api/cms/{path:path}")
async def options_cms_routes(request: Request, path: str):
    """
    Explicit OPTIONS handler for all CMS routes.
    Handles CORS preflight requests for all allowed origins.
    This catches all OPTIONS requests to /api/cms/* routes.
    """
    origin = request.headers.get("origin", "No origin")
    access_control_request_method = request.headers.get("access-control-request-method", "POST")
    access_control_request_headers = request.headers.get("access-control-request-headers", "*")
    
    logger.info(
        f"Explicit OPTIONS handler called for /api/cms/{path}\n"
        f"  Origin: {origin}\n"
        f"  Access-Control-Request-Method: {access_control_request_method}\n"
        f"  Access-Control-Request-Headers: {access_control_request_headers}\n"
        f"  All headers: {dict(request.headers)}"
    )
    
    # Determine allowed origin
    if origin == "No origin":
        # No origin header - allow with wildcard (for same-origin requests)
        allow_origin = "*"
    elif origin == "null":
        # Null origin (file:// protocol)
        allow_origin = "null"
    elif origin in cors_origins:
        # Origin is in allowed list
        allow_origin = origin
    else:
        # Origin not in allowed list - still allow but log warning
        logger.warning(f"OPTIONS request from unlisted origin: {origin}")
        allow_origin = origin  # Allow it anyway for now
    
    # Return empty response with CORS headers
    return JSONResponse(
        content={},
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": access_control_request_headers or "*",
            "Access-Control-Expose-Headers": "*",
            "Access-Control-Max-Age": "3600",
        }
    )


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

