"""
CMS API routes with password authentication.
All endpoints require password authentication via header.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.sql import func
from typing import Optional, List
import logging
import re
import asyncio

from app.database import get_db
from app.models import GalleryImage
from app.schemas import GalleryImageResponse, GalleryImageUpdate, BulkDeleteRequest, ImageReorderRequest
from app.utils.auth import verify_admin_password
from app.utils.image_converter import convert_to_webp
from app.services.cloudinary_service import upload_image, delete_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cms", tags=["CMS"])


def verify_cms_password(
    x_cms_password: Optional[str] = Header(None, alias="X-CMS-Password", description="CMS admin password")
) -> bool:
    """
    FastAPI dependency for CMS password authentication.
    
    Args:
        x_cms_password: Password provided in request header (X-CMS-Password)
    
    Returns:
        True if authenticated
    
    Raises:
        HTTPException: 401 if password is invalid or missing
    """
    if not x_cms_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Missing password", "message": "CMS access requires password authentication"}
        )
    
    try:
        if not verify_admin_password(x_cms_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "Invalid password", "message": "CMS access denied"}
            )
    except ValueError as e:
        # ADMIN_PASSWORD_HASH not configured
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Authentication not configured", "message": str(e)}
        )
    
    return True


def extract_public_id_from_url(cloudinary_url: str) -> str:
    """
    Extract Cloudinary public_id from URL.
    
    Cloudinary URLs typically look like:
    https://res.cloudinary.com/{cloud_name}/image/upload/v{version}/{public_id}.{format}
    or
    https://res.cloudinary.com/{cloud_name}/image/upload/{public_id}.{format}
    
    Args:
        cloudinary_url: Full Cloudinary URL
    
    Returns:
        str: Public ID (e.g., "gallery/image" without file extension)
    
    Raises:
        ValueError: If URL format is invalid
    """
    # Pattern to match Cloudinary URL structure
    # Matches: /image/upload/v{version}/ or /image/upload/ followed by public_id (which may include folders)
    # Captures everything after /image/upload/ (or /image/upload/v{version}/) until the end
    pattern = r'/image/upload(?:/v\d+)?/(.+)$'
    match = re.search(pattern, cloudinary_url)
    
    if not match:
        raise ValueError(f"Invalid Cloudinary URL format: {cloudinary_url}")
    
    public_id_with_ext = match.group(1)
    
    # Remove file extension from the last segment (public_id should not include extension)
    # Example: "gallery/image.jpg" -> "gallery/image"
    # Example: "image.jpg" -> "image"
    # Handle both folder paths and direct filenames
    if '.' in public_id_with_ext:
        # Split by '/' to handle folder paths
        parts = public_id_with_ext.split('/')
        # Remove extension from the last part (filename)
        if len(parts) > 0:
            last_part = parts[-1]
            if '.' in last_part:
                # Remove extension from filename
                parts[-1] = last_part.rsplit('.', 1)[0]
                return '/'.join(parts)
    
    return public_id_with_ext


@router.get("/gallery-images", response_model=list[GalleryImageResponse])
async def get_cms_gallery_images(
    db: AsyncSession = Depends(get_db),
    authenticated: bool = Depends(verify_cms_password)
):
    """
    Get all gallery images for CMS dashboard.
    Requires password authentication.
    
    Returns gallery images ordered by creation date (newest first).
    
    Args:
        db: Database session (injected by FastAPI dependency)
        authenticated: Authentication status (injected by dependency)
    
    Returns:
        list[GalleryImageResponse]: List of gallery images with metadata
    
    Raises:
        HTTPException: 500 if database query fails
    """
    try:
        # Query all gallery images, ordered by display_order ascending (custom order)
        result = await db.execute(
            select(GalleryImage).order_by(GalleryImage.display_order.asc())
        )
        images = result.scalars().all()
        
        logger.info(f"Retrieved {len(images)} gallery images for CMS")
        
        # Convert SQLAlchemy models to Pydantic schemas
        return [GalleryImageResponse.model_validate(img) for img in images]
        
    except Exception as e:
        logger.error(f"Error fetching CMS gallery images: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to retrieve gallery images", "detail": str(e)}
        )


@router.post("/gallery-images", response_model=List[GalleryImageResponse], status_code=status.HTTP_201_CREATED)
async def add_cms_gallery_images(
    request: Request,
    db: AsyncSession = Depends(get_db),
    authenticated: bool = Depends(verify_cms_password)
):
    """
    Add one or more gallery images (single or bulk upload).
    Requires password authentication.
    Uploads images to Cloudinary and saves metadata to database.
    
    Args:
        request: FastAPI Request object to parse multipart form data
        db: Database session (injected by FastAPI dependency)
        authenticated: Authentication status (injected by dependency)
    
    Returns:
        List[GalleryImageResponse]: Created images with metadata
    
    Raises:
        HTTPException: 400 if files are invalid, 500 if upload or save fails
    """
    try:
        # Parse multipart form data
        form = await request.form()
        
        # Get all files (they all have the same field name "files")
        files = form.getlist("files")
        
        if not files or len(files) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "No files provided", "detail": "At least one image file is required"}
            )
        
        # Get captions if provided (one per file)
        caption_list = []
        captions = form.getlist("captions")
        if captions:
            caption_list = [c.strip() if isinstance(c, str) and c.strip() else None for c in captions]
        
        # Validate all files first
        for i, file in enumerate(files):
            if not hasattr(file, 'content_type') or not file.content_type or not file.content_type.startswith('image/'):
                filename = getattr(file, 'filename', f'file_{i}')
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Invalid file type", "detail": f"File '{filename}' is not a valid image file"}
                )
        
        # Step 1: Process Cloudinary uploads concurrently (no DB session needed)
        # This avoids session conflicts while maintaining performance
        upload_tasks = []
        for i, file in enumerate(files):
            # Get caption for this file (one caption per file, by index)
            caption = None
            if caption_list and i < len(caption_list):
                caption = caption_list[i] if caption_list[i] else None
            
            # Create upload task (only Cloudinary upload, no DB operations)
            task = _upload_to_cloudinary_and_convert(file, caption)
            upload_tasks.append(task)
        
        # Execute all Cloudinary uploads concurrently
        upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)
        
        # Step 2: Process database operations sequentially (using main session)
        # This avoids session concurrency issues
        created_images = []
        errors = []
        
        for i, upload_result in enumerate(upload_results):
            filename = getattr(files[i], 'filename', f'file_{i}')
            
            if isinstance(upload_result, Exception):
                error_msg = str(upload_result)
                logger.error(f"Error uploading file {filename}: {error_msg}")
                errors.append({
                    "filename": filename,
                    "error": error_msg
                })
            else:
                # Upload succeeded, now save to database
                try:
                    cloudinary_url = upload_result["cloudinary_url"]
                    caption = upload_result["caption"]
                    
                    # Get the current maximum display_order
                    max_order_result = await db.execute(
                        select(func.max(GalleryImage.display_order))
                    )
                    max_order = max_order_result.scalar() or 0
                    
                    # Save to database with next display_order
                    new_image = GalleryImage(
                        cloudinary_url=cloudinary_url,
                        caption=caption.strip() if caption and caption.strip() else None,
                        display_order=max_order + 1
                    )
                    db.add(new_image)
                    await db.flush()  # Flush to get ID but don't commit yet
                    await db.refresh(new_image)
                    
                    created_images.append(new_image)
                    logger.info(f"Successfully saved image to database: ID {new_image.id}, display_order={new_image.display_order}")
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error saving file {filename} to database: {error_msg}")
                    errors.append({
                        "filename": filename,
                        "error": f"Database error: {error_msg}"
                    })
        
        # If all uploads failed, rollback and return error
        if len(created_images) == 0:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "All uploads failed",
                    "errors": errors
                }
            )
        
        # Commit all successful uploads at once
        await db.commit()
        
        # Refresh all images to get final state
        for img in created_images:
            await db.refresh(img)
        
        # Log partial success if some failed
        if len(errors) > 0:
            logger.warning(f"Partial upload success: {len(created_images)} succeeded, {len(errors)} failed")
        
        logger.info(f"Successfully uploaded {len(created_images)} image(s)")
        
        return [GalleryImageResponse.model_validate(img) for img in created_images]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding gallery images: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to add gallery images", "detail": str(e)}
        )


async def _upload_to_cloudinary_and_convert(
    file: UploadFile,
    caption: Optional[str]
) -> dict:
    """
    Upload a single image to Cloudinary and convert to WebP if beneficial.
    This function does NOT interact with the database to avoid session conflicts.
    Helper function for bulk uploads.
    
    Args:
        file: Image file to upload
        caption: Optional caption for the image
    
    Returns:
        dict: Contains "cloudinary_url" and "caption" keys
    
    Raises:
        Exception: If upload or conversion fails
    """
    try:
        # Read file content
        # For files from form data, we need to read the content
        file_content = await file.read()
        
        filename = getattr(file, 'filename', 'unknown')
        
        # Convert to WebP format to reduce file size before upload
        # Falls back to original if conversion fails
        converted_content, conversion_success = await convert_to_webp(
            file_content,
            quality=85,  # Good balance between quality and file size
            skip_if_webp=True  # Skip if already WebP
        )
        
        if conversion_success:
            original_size = len(file_content)
            converted_size = len(converted_content)
            if converted_size < original_size:
                logger.info(
                    f"Converted {filename} to WebP: "
                    f"{original_size:,} bytes → {converted_size:,} bytes"
                )
                file_content = converted_content
            else:
                logger.debug(f"WebP conversion did not reduce size for {filename}, using original")
                file_content = file_content  # Use original if WebP is larger
        else:
            logger.warning(f"WebP conversion failed for {filename}, uploading original format")
            # Use original file_content if conversion failed
        
        # Upload to Cloudinary (pass file content as bytes)
        logger.info(f"Uploading image to Cloudinary: {filename}")
        cloudinary_result = await upload_image(file_content, folder="gallery")
        cloudinary_url = cloudinary_result["url"]
        
        logger.info(f"Successfully uploaded to Cloudinary: {cloudinary_url}")
        
        return {
            "cloudinary_url": cloudinary_url,
            "caption": caption
        }
        
    except Exception as e:
        logger.error(f"Error processing image upload for {file.filename}: {str(e)}")
        raise


@router.put("/gallery-images/reorder")
async def reorder_gallery_images(
    request: ImageReorderRequest,
    db: AsyncSession = Depends(get_db),
    authenticated: bool = Depends(verify_cms_password)
):
    """
    Reorder gallery images by updating display_order.
    Requires password authentication.

    The frontend sends an array of image IDs in the desired display order.
    This endpoint updates each image's display_order to match the array index.

    Args:
        request: ImageReorderRequest containing ordered list of image IDs
        db: Database session (injected by FastAPI dependency)
        authenticated: Authentication status (injected by dependency)

    Returns:
        dict: Success message with count of reordered images

    Raises:
        HTTPException: 400 if invalid IDs, 404 if images not found, 500 if update fails
    """
    try:
        image_ids = request.image_ids

        if not image_ids or len(image_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "No image IDs provided", "detail": "At least one image ID is required"}
            )

        # Verify all images exist
        result = await db.execute(
            select(GalleryImage).where(GalleryImage.id.in_(image_ids))
        )
        existing_images = result.scalars().all()
        existing_ids = {img.id for img in existing_images}

        # Check for missing IDs
        missing_ids = set(image_ids) - existing_ids
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Images not found",
                    "detail": f"Image IDs not found: {list(missing_ids)}"
                }
            )

        # Get ALL images to handle reordering properly
        # If only a subset is provided, we need to adjust all images
        all_images_result = await db.execute(
            select(GalleryImage).order_by(GalleryImage.display_order.asc())
        )
        all_images = all_images_result.scalars().all()
        all_image_ids = {img.id for img in all_images}
        
        # Create a set of IDs that are being reordered
        reordered_ids = set(image_ids)
        
        # Build the final ordered list:
        # 1. Reordered images in the order provided
        # 2. Remaining images in their current relative order
        final_ordered_ids = []
        final_ordered_ids.extend(image_ids)  # Add reordered images first
        
        # Add remaining images that weren't in the reorder request
        # Maintain their current relative order
        for img in all_images:
            if img.id not in reordered_ids:
                final_ordered_ids.append(img.id)

        # Update display_order for ALL images to ensure no conflicts
        # This prevents gaps or overlapping display_order values
        for position, image_id in enumerate(final_ordered_ids):
            await db.execute(
                update(GalleryImage)
                .where(GalleryImage.id == image_id)
                .values(display_order=position)
            )

        await db.commit()

        logger.info(f"Successfully reordered {len(image_ids)} images")

        return {
            "message": f"Successfully reordered {len(image_ids)} images",
            "count": len(image_ids)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reordering gallery images: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to reorder gallery images", "detail": str(e)}
        )


@router.put("/gallery-images/{image_id}", response_model=GalleryImageResponse)
async def update_cms_gallery_image(
    image_id: int,
    image_update: GalleryImageUpdate,
    db: AsyncSession = Depends(get_db),
    authenticated: bool = Depends(verify_cms_password)
):
    """
    Update an existing gallery image caption.
    Requires password authentication.
    
    Args:
        image_id: Image ID to update
        image_update: Update data containing caption (optional, can be null to clear caption)
        db: Database session (injected by FastAPI dependency)
        authenticated: Authentication status (injected by dependency)
    
    Returns:
        GalleryImageResponse: Updated image with metadata
    
    Raises:
        HTTPException: 404 if image not found, 500 if update fails
    """
    try:
        # Query image by ID
        result = await db.execute(
            select(GalleryImage).where(GalleryImage.id == image_id)
        )
        image = result.scalar_one_or_none()
        
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Image not found", "detail": f"Image ID {image_id} does not exist"}
            )
        
        # Update caption
        caption = image_update.caption
        image.caption = caption.strip() if caption and caption.strip() else None
        await db.commit()
        await db.refresh(image)
        
        logger.info(f"Successfully updated image caption: ID {image_id}")
        
        return GalleryImageResponse.model_validate(image)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating gallery image: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to update gallery image", "detail": str(e)}
        )


@router.delete("/gallery-images/bulk")
async def delete_cms_gallery_images_bulk(
    request: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    authenticated: bool = Depends(verify_cms_password)
):
    """
    Delete multiple gallery images at once (bulk delete).
    Requires password authentication.
    Deletes from both database and Cloudinary.
    
    Args:
        image_ids: List of image IDs to delete
        db: Database session (injected by FastAPI dependency)
        authenticated: Authentication status (injected by dependency)
    
    Returns:
        dict: Success message with deleted image IDs and any errors
    
    Raises:
        HTTPException: 400 if no IDs provided, 500 if deletion fails
    """
    try:
        image_ids = request.image_ids
        
        if not image_ids or len(image_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "No image IDs provided", "detail": "At least one image ID is required"}
            )
        
        # Get all images from database
        result = await db.execute(
            select(GalleryImage).where(GalleryImage.id.in_(image_ids))
        )
        images = result.scalars().all()
        
        if not images:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "No images found", "detail": f"None of the provided image IDs were found"}
            )
        
        # Step 1: Process Cloudinary deletions concurrently (no DB session needed)
        # This avoids session conflicts while maintaining performance
        delete_tasks = []
        for image in images:
            # Create deletion task (only Cloudinary deletion, no DB operations)
            task = _delete_from_cloudinary(image)
            delete_tasks.append(task)
        
        # Execute all Cloudinary deletions concurrently
        delete_results = await asyncio.gather(*delete_tasks, return_exceptions=True)
        
        # Step 2: Process database operations sequentially (using main session)
        # This avoids session concurrency issues
        deleted_ids = []
        errors = []
        
        for i, delete_result in enumerate(delete_results):
            image = images[i]
            
            if isinstance(delete_result, Exception):
                error_msg = str(delete_result)
                logger.error(f"Error deleting from Cloudinary for image {image.id}: {error_msg}")
                # Continue with database deletion even if Cloudinary deletion fails
                # But log the error for debugging
            
            # Delete from database (always attempt, even if Cloudinary deletion failed)
            try:
                await db.execute(
                    delete(GalleryImage).where(GalleryImage.id == image.id)
                )
                deleted_ids.append(image.id)
                logger.info(f"Successfully deleted image from database: ID {image.id}")
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error deleting image {image.id} from database: {error_msg}")
                errors.append({
                    "image_id": image.id,
                    "error": f"Database error: {error_msg}"
                })
        
        # If all deletions failed, rollback and return error
        if len(deleted_ids) == 0:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "All deletions failed",
                    "errors": errors
                }
            )
        
        # Commit all successful deletions at once
        await db.commit()
        
        # Log partial success if some failed
        if len(errors) > 0:
            logger.warning(f"Partial deletion success: {len(deleted_ids)} succeeded, {len(errors)} failed")
        
        logger.info(f"Successfully deleted {len(deleted_ids)} image(s)")
        
        return {
            "message": f"Deleted {len(deleted_ids)} image(s) successfully",
            "deleted_ids": deleted_ids,
            "errors": errors if errors else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting gallery images: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to delete gallery images", "detail": str(e)}
        )


async def _delete_from_cloudinary(
    image: GalleryImage
) -> None:
    """
    Delete a single image from Cloudinary.
    This function does NOT interact with the database to avoid session conflicts.
    Helper function for bulk deletions.
    
    Args:
        image: GalleryImage model to delete from Cloudinary
    
    Raises:
        Exception: If Cloudinary deletion fails
    """
    try:
        # Extract Cloudinary public_id from URL
        cloudinary_public_id = None
        try:
            cloudinary_public_id = extract_public_id_from_url(image.cloudinary_url)
            logger.info(f"Extracted public_id: {cloudinary_public_id} from URL: {image.cloudinary_url}")
        except ValueError as e:
            logger.warning(f"Failed to extract public_id from URL: {str(e)}")
            raise ValueError(f"Could not extract public_id from URL: {image.cloudinary_url}")
        
        # Delete from Cloudinary
        if cloudinary_public_id:
            result = await delete_image(cloudinary_public_id)
            logger.info(f"Successfully deleted from Cloudinary: {cloudinary_public_id}, result: {result}")
        else:
            raise ValueError(f"No public_id extracted for image ID {image.id}")
        
    except Exception as e:
        logger.error(f"Error deleting from Cloudinary for image ID {image.id}: {str(e)}", exc_info=True)
        raise


@router.delete("/gallery-images/{image_id}")
async def delete_cms_gallery_image(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    authenticated: bool = Depends(verify_cms_password)
):
    """
    Delete a gallery image.
    Requires password authentication.
    Deletes from both database and Cloudinary.
    
    Args:
        image_id: Image ID to delete
        db: Database session (injected by FastAPI dependency)
        authenticated: Authentication status (injected by dependency)
    
    Returns:
        dict: Success message with image ID
    
    Raises:
        HTTPException: 404 if image not found, 500 if deletion fails
    """
    try:
        # Get image from database
        result = await db.execute(
            select(GalleryImage).where(GalleryImage.id == image_id)
        )
        image = result.scalar_one_or_none()
        
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Image not found", "detail": f"Image ID {image_id} does not exist"}
            )
        
        # Extract Cloudinary public_id from URL
        try:
            cloudinary_public_id = extract_public_id_from_url(image.cloudinary_url)
            logger.info(f"Extracted public_id: {cloudinary_public_id} from URL: {image.cloudinary_url}")
        except ValueError as e:
            logger.warning(f"Failed to extract public_id from URL: {str(e)}")
            cloudinary_public_id = None
        
        # Delete from Cloudinary (if public_id was extracted)
        if cloudinary_public_id:
            try:
                result = await delete_image(cloudinary_public_id)
                logger.info(f"Successfully deleted from Cloudinary: {cloudinary_public_id}, result: {result}")
            except Exception as e:
                logger.error(f"Failed to delete from Cloudinary for image ID {image_id} (public_id: {cloudinary_public_id}): {str(e)}", exc_info=True)
                # Continue with database deletion even if Cloudinary deletion fails
                # But log the error for debugging
        else:
            logger.warning(f"Could not extract public_id from URL: {image.cloudinary_url}, skipping Cloudinary deletion for image ID {image_id}")
        
        # Delete from database
        await db.execute(
            delete(GalleryImage).where(GalleryImage.id == image_id)
        )
        await db.commit()
        
        logger.info(f"Successfully deleted image from database: ID {image_id}")
        
        return {"message": "Image deleted successfully", "image_id": image_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting gallery image: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to delete gallery image", "detail": str(e)}
        )
