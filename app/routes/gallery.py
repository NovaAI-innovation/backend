"""
Gallery routes for public gallery image retrieval.
Provides endpoints for fetching gallery images to display in the frontend.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import logging

from app.database import get_db
from app.models import GalleryImage
from app.schemas import GalleryImageResponse

logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()


@router.get("/gallery-images", response_model=List[GalleryImageResponse])
async def get_gallery_images(db: AsyncSession = Depends(get_db)):
    """
    Get all gallery images.

    Returns gallery images ordered by creation date (newest first).
    This is a public endpoint accessible without authentication.

    Args:
        db: Database session (injected by FastAPI dependency)

    Returns:
        List[GalleryImageResponse]: List of gallery images with metadata

    Raises:
        HTTPException: 500 if database query fails
    """
    try:
        # Query all gallery images, ordered by created_at descending (newest first)
        result = await db.execute(
            select(GalleryImage).order_by(GalleryImage.created_at.desc())
        )
        images = result.scalars().all()

        logger.info(f"Retrieved {len(images)} gallery images")

        # Convert SQLAlchemy models to Pydantic schemas
        # Pydantic automatically handles JSON serialization and date formatting
        return [GalleryImageResponse.model_validate(img) for img in images]

    except Exception as e:
        logger.error(f"Failed to retrieve gallery images: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to retrieve gallery images",
                "detail": str(e)
            }
        )
