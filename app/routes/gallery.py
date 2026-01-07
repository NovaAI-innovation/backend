"""
Gallery routes for public gallery image retrieval.
Provides endpoints for fetching gallery images to display in the frontend.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import logging

from app.database import get_db
from app.models import GalleryImage
from app.schemas import GalleryImageResponse, GalleryImagesPageResponse, GalleryImagePublicResponse, PaginationMetadata

logger = logging.getLogger(__name__)

# Create router instance
router = APIRouter()


@router.get("/gallery-images", response_model=GalleryImagesPageResponse)
async def get_gallery_images(
    limit: int = 12,
    cursor: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get paginated gallery images.

    Implements cursor-based pagination using display_order field.
    Returns images ordered by display_order ascending.

    Args:
        limit: Number of images to return (default: 12, max: 100)
        cursor: Last display_order from previous page (for pagination)
        db: Database session (injected by FastAPI dependency)

    Returns:
        GalleryImagesPageResponse: Paginated images with metadata

    Raises:
        HTTPException: 400 if invalid parameters, 500 if database query fails
    """
    try:
        # Validate limit
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be between 1 and 100"
            )

        # Build query with cursor-based pagination
        query = select(GalleryImage).order_by(GalleryImage.display_order.asc())

        if cursor is not None:
            # Get images after the cursor
            query = query.where(GalleryImage.display_order > cursor)

        # Fetch limit + 1 to determine if there are more results
        query = query.limit(limit + 1)
        result = await db.execute(query)
        images = result.scalars().all()

        # Check if there are more results
        has_more = len(images) > limit
        if has_more:
            images = images[:limit]  # Remove the extra record

        # Determine next cursor
        next_cursor = images[-1].display_order if images and has_more else None

        # Get total count
        count_result = await db.execute(select(func.count(GalleryImage.id)))
        total_count = count_result.scalar()

        logger.info(
            f"Retrieved {len(images)} gallery images "
            f"(cursor: {cursor}, next: {next_cursor}, has_more: {has_more})"
        )

        return GalleryImagesPageResponse(
            images=[GalleryImagePublicResponse.model_validate(img) for img in images],
            pagination=PaginationMetadata(
                next_cursor=next_cursor,
                has_more=has_more,
                total_count=total_count
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve gallery images: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to retrieve gallery images",
                "detail": str(e)
            }
        )
