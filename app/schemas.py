"""
Pydantic schemas for request and response data validation.
Defines data structures for API endpoints with automatic validation and serialization.
"""
from pydantic import BaseModel, ConfigDict, field_validator
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
    display_order: int
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


class ImageReorderRequest(BaseModel):
    """
    Request schema for reordering gallery images.
    Used by PUT /api/cms/gallery-images/reorder endpoint.
    Contains array of image IDs in the desired display order.
    """
    image_ids: list[int]

    @field_validator('image_ids')
    @classmethod
    def validate_unique_ids(cls, v):
        if len(v) != len(set(v)):
            raise ValueError('Duplicate image IDs are not allowed')
        return v
