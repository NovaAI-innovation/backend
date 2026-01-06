"""
Database connection and session management for SQLAlchemy 2.0.
Configured for async operations with Supabase PostgreSQL.
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from urllib.parse import urlparse
import logging
import socket

from app.config import settings

logger = logging.getLogger(__name__)

# Create declarative base for models
Base = declarative_base()

# Create async engine with connection pooling
# Connection pooling configured for efficient database access
# Pool settings only apply to PostgreSQL (not SQLite)
_engine_args = {
    "echo": False,  # Set to True for SQL query logging in development
}

# Add PostgreSQL-specific connection pooling if using PostgreSQL
if settings.DATABASE_URL and settings.DATABASE_URL.startswith("postgresql"):
    _engine_args.update({
        "pool_size": 10,  # Number of connections to maintain in pool
        "max_overflow": 20,  # Additional connections allowed beyond pool_size
        "pool_pre_ping": True,  # Verify connections before using (handles stale connections)
        "pool_recycle": 3600,  # Recycle connections after 1 hour (prevents stale connections)
        "connect_args": {
            "server_settings": {
                "application_name": "mm-bmad-v2-backend"
            }
        }
    })

engine = create_async_engine(
    settings.DATABASE_URL if settings.DATABASE_URL else "sqlite+aiosqlite:///:memory:",
    **_engine_args
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """
    FastAPI dependency for database sessions.
    Provides async database session with automatic commit/rollback.
    
    Usage:
        @app.get("/endpoint")
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            # Use db session here
            pass
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {str(e)}", exc_info=True)
            raise
        finally:
            await session.close()


def _validate_database_url(url: str) -> tuple[bool, str]:
    """
    Validate database URL and provide diagnostic information.
    Returns (is_valid, diagnostic_message)
    """
    if not url:
        return False, "DATABASE_URL is empty"
    
    try:
        parsed = urlparse(url)
        
        # Check if it's a PostgreSQL URL
        if not url.startswith(("postgresql://", "postgresql+asyncpg://")):
            return False, f"Invalid database URL scheme. Expected postgresql:// or postgresql+asyncpg://, got: {parsed.scheme}"
        
        # Extract hostname
        hostname = parsed.hostname
        if not hostname:
            return False, "No hostname found in DATABASE_URL"
        
        # Try DNS resolution
        try:
            # Try to resolve hostname
            socket.getaddrinfo(hostname, None)
            dns_status = "DNS resolution successful"
        except socket.gaierror as e:
            dns_status = f"DNS resolution failed: {str(e)}. This may indicate network connectivity issues or incorrect hostname."
        except Exception as e:
            dns_status = f"DNS resolution error: {str(e)}"
        
        return True, f"URL format valid. Hostname: {hostname}, Port: {parsed.port or 5432}, Database: {parsed.path or '/postgres'}. {dns_status}"
    
    except Exception as e:
        return False, f"Error parsing DATABASE_URL: {str(e)}"


async def init_db():
    """
    Initialize database connection.
    Can be used for startup events to verify connection.
    """
    if not settings.DATABASE_URL:
        logger.warning("DATABASE_URL not set, skipping database initialization")
        return
    
    # Validate URL and provide diagnostics
    is_valid, diagnostic = _validate_database_url(settings.DATABASE_URL)
    if not is_valid:
        logger.error(f"Invalid DATABASE_URL: {diagnostic}")
        raise ValueError(f"Invalid DATABASE_URL: {diagnostic}")
    
    logger.info(f"Database URL validation: {diagnostic}")
    
    try:
        async with engine.begin() as conn:
            # Test connection with a simple query
            await conn.execute(text("SELECT 1"))
            logger.info("Database connection initialized successfully")
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        
        # Provide more detailed error information
        if "getaddrinfo failed" in error_msg or "11001" in error_msg:
            logger.error(
                f"Database connection failed - DNS resolution error: {error_msg}\n"
                f"This usually means:\n"
                f"  1. The hostname in DATABASE_URL cannot be resolved\n"
                f"  2. Network connectivity issues\n"
                f"  3. Firewall blocking the connection\n"
                f"  4. IPv6/IPv4 compatibility issues\n"
                f"Diagnostic: {diagnostic}"
            )
        elif "connection refused" in error_msg.lower() or "connection timeout" in error_msg.lower():
            logger.error(
                f"Database connection failed - Connection refused/timeout: {error_msg}\n"
                f"This usually means:\n"
                f"  1. The database server is not accessible\n"
                f"  2. Firewall is blocking the connection\n"
                f"  3. The port is incorrect\n"
                f"Diagnostic: {diagnostic}"
            )
        elif "authentication failed" in error_msg.lower() or "password" in error_msg.lower():
            logger.error(
                f"Database connection failed - Authentication error: {error_msg}\n"
                f"This usually means:\n"
                f"  1. Incorrect username or password in DATABASE_URL\n"
                f"  2. Database user does not have required permissions\n"
                f"Diagnostic: {diagnostic}"
            )
        else:
            logger.error(
                f"Database connection failed ({error_type}): {error_msg}\n"
                f"Diagnostic: {diagnostic}"
            )
        raise


async def close_db():
    """
    Close database connections.
    Can be used for shutdown events.
    """
    await engine.dispose()
    logger.info("Database connections closed")

