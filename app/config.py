"""
Configuration management for the FastAPI application.
Uses Pydantic Settings for environment variable management.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    API_TITLE: str = "Makayla Moon API"
    API_VERSION: str = "0.1.0"
    API_DESCRIPTION: str = "Backend API for showcase gallery and booking portal"
    
    # CORS Configuration
    # Allow GitHub Pages origins and common local development ports
    # For development, you can use ["*"] to allow all origins (not recommended for production)
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5500",
        "http://localhost:8080",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8000",
        "http://localhost",
        "http://127.0.0.1",
        "https://novaai-innovation.github.io",
        "*",  # Allow all origins - use specific URLs in production
    ]
    
    # Database Configuration (will be used in Story 2.2)
    DATABASE_URL: str = ""
    
    # Cloudinary Configuration (will be used in Story 2.4)
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    
    # Admin Password (will be used in Epic 4)
    # Should be bcrypt hashed password
    ADMIN_PASSWORD_HASH: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env that aren't defined in Settings


# Global settings instance
settings = Settings()


