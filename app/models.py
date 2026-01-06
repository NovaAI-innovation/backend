"""
SQLAlchemy models for the application.
All database models inherit from Base (declarative base).
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base


class GalleryImage(Base):
    """
    Gallery image model.
    Stores image metadata including Cloudinary URL and caption.
    """
    __tablename__ = "gallery_images"

    id = Column(Integer, primary_key=True, index=True)
    cloudinary_url = Column(String, nullable=False)
    caption = Column(String, nullable=True)
    display_order = Column(Integer, nullable=False, default=0, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

