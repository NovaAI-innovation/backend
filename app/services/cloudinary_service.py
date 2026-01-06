"""
Cloudinary service for image upload, optimization, and management.
Provides functions for uploading images with automatic optimization and CDN delivery.
"""
import cloudinary
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError
from app.config import settings
import logging
import asyncio
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Configure Cloudinary with credentials from settings
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True  # Always use HTTPS for secure URLs
)


async def upload_image(
    file: Any,
    folder: str = "gallery",
    public_id: Optional[str] = None,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Upload image to Cloudinary with automatic optimization and retry logic.

    Args:
        file: File object, file path, or bytes to upload
        folder: Cloudinary folder path (default: "gallery")
        public_id: Optional custom public ID for the image
        max_retries: Maximum number of retry attempts for transient failures

    Returns:
        dict: Upload result containing:
            - url: Secure HTTPS URL for the uploaded image
            - public_id: Cloudinary public ID
            - format: Image format (jpg, png, webp, etc.)
            - width: Image width in pixels
            - height: Image height in pixels
            - bytes: File size in bytes

    Raises:
        CloudinaryError: If upload fails after all retries
        Exception: For unexpected errors
    """
    for attempt in range(max_retries):
        try:
            # Upload with automatic optimization
            result = cloudinary.uploader.upload(
                file,
                folder=folder,
                public_id=public_id,
                # Automatic optimization settings
                fetch_format="auto",  # Auto-select best format (WebP, AVIF, etc.)
                quality="auto",  # Automatic quality optimization and compression
                # Transformation options
                transformation=[
                    {
                        "width": 1920,
                        "height": 1080,
                        "crop": "limit"  # Limit max dimensions, maintain aspect ratio
                    }
                ]
            )

            logger.info(f"Successfully uploaded image: {result['public_id']}")

            return {
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "format": result["format"],
                "width": result["width"],
                "height": result["height"],
                "bytes": result["bytes"]
            }

        except CloudinaryError as e:
            logger.warning(f"Cloudinary upload error (attempt {attempt + 1}/{max_retries}): {str(e)}")

            # Retry with exponential backoff for transient failures
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s backoff
                continue

            # All retries exhausted
            logger.error(f"Cloudinary upload failed after {max_retries} attempts: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error during image upload: {str(e)}", exc_info=True)
            raise


async def delete_image(public_id: str, max_retries: int = 3) -> Dict[str, Any]:
    """
    Delete image from Cloudinary with retry logic.

    Args:
        public_id: Cloudinary public ID of the image to delete
        max_retries: Maximum number of retry attempts for transient failures

    Returns:
        dict: Deletion result from Cloudinary

    Raises:
        CloudinaryError: If deletion fails after all retries
        Exception: For unexpected errors
    """
    for attempt in range(max_retries):
        try:
            # Delete with CDN invalidation to ensure asset is removed from cache
            result = cloudinary.uploader.destroy(
                public_id,
                invalidate=True,  # Invalidate CDN cache
                resource_type='image'  # Explicitly specify resource type
            )

            # Check if deletion was successful
            if result.get('result') == 'ok' or result.get('result') == 'not found':
                logger.info(f"Successfully deleted image from Cloudinary: {public_id} (result: {result.get('result')})")
                return result
            else:
                logger.warning(f"Unexpected Cloudinary delete result for {public_id}: {result}")
                return result

        except CloudinaryError as e:
            logger.warning(f"Cloudinary delete error (attempt {attempt + 1}/{max_retries}) for {public_id}: {str(e)}")

            # Retry with exponential backoff for transient failures
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s backoff
                continue

            # All retries exhausted
            logger.error(f"Cloudinary delete failed after {max_retries} attempts for {public_id}: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error during image deletion for {public_id}: {str(e)}", exc_info=True)
            raise


def get_optimized_url(
    public_id: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    quality: str = "auto",
    fetch_format: str = "auto"
) -> str:
    """
    Generate optimized Cloudinary URL with transformations.

    Args:
        public_id: Cloudinary public ID
        width: Optional width for transformation
        height: Optional height for transformation
        quality: Quality setting (auto, best, good, eco, low)
        fetch_format: Format setting (auto, jpg, png, webp, etc.)

    Returns:
        str: Optimized Cloudinary URL with transformations
    """
    transformation = []

    if width or height:
        transform_params = {"crop": "limit"}
        if width:
            transform_params["width"] = width
        if height:
            transform_params["height"] = height
        transformation.append(transform_params)

    # Add quality and format optimization
    transformation.append({
        "quality": quality,
        "fetch_format": fetch_format
    })

    url = cloudinary.CloudinaryImage(public_id).build_url(
        transformation=transformation,
        secure=True
    )

    return url


def validate_cloudinary_config() -> bool:
    """
    Validate that Cloudinary is properly configured.

    Returns:
        bool: True if Cloudinary is configured, False otherwise
    """
    if not settings.CLOUDINARY_CLOUD_NAME:
        logger.warning("CLOUDINARY_CLOUD_NAME not configured")
        return False
    if not settings.CLOUDINARY_API_KEY:
        logger.warning("CLOUDINARY_API_KEY not configured")
        return False
    if not settings.CLOUDINARY_API_SECRET:
        logger.warning("CLOUDINARY_API_SECRET not configured")
        return False

    logger.info("Cloudinary configuration validated successfully")
    return True
