"""
Pydantic schemas for request and response data validation.
Defines data structures for API endpoints with automatic validation and serialization.
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class GalleryImageResponse(BaseModel):
    """
    Response schema for gallery image data.
    Used by GET /api/gallery-images endpoint.
    """
    id: int
    cloudinary_url: str
    caption: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,  # Enable conversion from SQLAlchemy models
        json_encoders={
            datetime: lambda v: v.isoformat()  # Format dates as ISO 8601 strings
        }
    )


class GalleryImageCreate(BaseModel):
    """
    Request schema for creating new gallery images.
    Used by POST /api/cms/gallery-images endpoint (Epic 4).
    """
    cloudinary_url: str
    caption: Optional[str] = None


class GalleryImageUpdate(BaseModel):
    """
    Request schema for updating gallery image captions.
    Used by PUT /api/cms/gallery-images/{id} endpoint (Epic 4).
    """
    caption: Optional[str] = None


class BulkDeleteRequest(BaseModel):
    """
    Request schema for bulk deleting gallery images.
    Used by DELETE /api/cms/gallery-images/bulk endpoint.
    """
    image_ids: list[int]
