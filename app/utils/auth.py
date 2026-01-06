"""
Password authentication utilities for CMS access.
Uses bcrypt for secure password hashing.
"""
import bcrypt
from app.config import settings
from fastapi import HTTPException, status


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    Used for generating the initial password hash.
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password string
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hashed password.
    
    Args:
        password: Plain text password to verify
        hashed_password: Hashed password to compare against
    
    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def verify_admin_password(password: str) -> bool:
    """
    Verify admin password against stored hash.
    
    Args:
        password: Plain text password to verify
    
    Returns:
        True if password matches admin password, False otherwise
    
    Raises:
        ValueError: If ADMIN_PASSWORD_HASH is not configured
    """
    if not settings.ADMIN_PASSWORD_HASH:
        raise ValueError("ADMIN_PASSWORD_HASH not configured")
    
    return verify_password(password, settings.ADMIN_PASSWORD_HASH)

