"""
CMS API routes with password authentication.
All endpoints require password authentication via header.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import logging
import re
import asyncio

from app.database import get_db
from app.models import GalleryImage
from app.schemas import GalleryImageResponse, GalleryImageUpdate, BulkDeleteRequest
from app.utils.auth import verify_admin_password
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
        # Query all gallery images, ordered by created_at descending (newest first)
        result = await db.execute(
            select(GalleryImage).order_by(GalleryImage.created_at.desc())
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
        
        # Get captions if provided
        caption_list = []
        captions = form.getlist("captions")
        if captions:
            caption_list = [c if isinstance(c, str) else str(c) for c in captions]
        
        # Validate all files first
        for i, file in enumerate(files):
            if not hasattr(file, 'content_type') or not file.content_type or not file.content_type.startswith('image/'):
                filename = getattr(file, 'filename', f'file_{i}')
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Invalid file type", "detail": f"File '{filename}' is not a valid image file"}
                )
        
        # Process uploads concurrently for better performance
        upload_tasks = []
        for i, file in enumerate(files):
            # Get caption for this file (if provided)
            caption = None
            if caption_list and i < len(caption_list):
                caption = caption_list[i]
            elif caption_list and len(caption_list) == 1:
                # If only one caption provided, apply to all files
                caption = caption_list[0]
            
            # Create upload task
            task = _process_single_image_upload(file, caption, db)
            upload_tasks.append(task)
        
        # Execute all uploads concurrently
        results = await asyncio.gather(*upload_tasks, return_exceptions=True)
        
        # Process results and handle errors
        created_images = []
        errors = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_msg = str(result)
                filename = getattr(files[i], 'filename', f'file_{i}')
                logger.error(f"Error uploading file {filename}: {error_msg}")
                errors.append({
                    "filename": filename,
                    "error": error_msg
                })
            else:
                created_images.append(result)
        
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


async def _process_single_image_upload(
    file: UploadFile,
    caption: Optional[str],
    db: AsyncSession
) -> GalleryImage:
    """
    Process a single image upload.
    Helper function for bulk uploads.
    
    Args:
        file: Image file to upload
        caption: Optional caption for the image
        db: Database session
    
    Returns:
        GalleryImage: Created image model
    
    Raises:
        Exception: If upload or save fails
    """
    try:
        # Read file content
        # For files from form data, we need to read the content
        file_content = await file.read()
        
        # Upload to Cloudinary (pass file content as bytes)
        filename = getattr(file, 'filename', 'unknown')
        logger.info(f"Uploading image to Cloudinary: {filename}")
        cloudinary_result = await upload_image(file_content, folder="gallery")
        cloudinary_url = cloudinary_result["url"]
        
        logger.info(f"Successfully uploaded to Cloudinary: {cloudinary_url}")
        
        # Save to database
        new_image = GalleryImage(
            cloudinary_url=cloudinary_url,
            caption=caption.strip() if caption and caption.strip() else None
        )
        db.add(new_image)
        await db.flush()  # Flush to get ID but don't commit yet
        await db.refresh(new_image)
        
        logger.info(f"Successfully saved image to database: ID {new_image.id}")
        
        return new_image
        
    except Exception as e:
        logger.error(f"Error processing image upload for {file.filename}: {str(e)}")
        raise


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
        
        # Process deletions concurrently
        delete_tasks = []
        for image in images:
            task = _process_single_image_deletion(image, db)
            delete_tasks.append(task)
        
        # Execute all deletions concurrently
        results = await asyncio.gather(*delete_tasks, return_exceptions=True)
        
        # Process results
        deleted_ids = []
        errors = []
        
        for i, result in enumerate(results):
            image = images[i]
            if isinstance(result, Exception):
                error_msg = str(result)
                logger.error(f"Error deleting image {image.id}: {error_msg}")
                errors.append({
                    "image_id": image.id,
                    "error": error_msg
                })
            else:
                deleted_ids.append(image.id)
        
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


async def _process_single_image_deletion(
    image: GalleryImage,
    db: AsyncSession
) -> None:
    """
    Process deletion of a single image.
    Helper function for bulk deletions.
    
    Args:
        image: GalleryImage model to delete
        db: Database session
    
    Raises:
        Exception: If deletion fails
    """
    try:
        # Extract Cloudinary public_id from URL
        cloudinary_public_id = None
        try:
            cloudinary_public_id = extract_public_id_from_url(image.cloudinary_url)
            logger.info(f"Extracted public_id: {cloudinary_public_id} from URL: {image.cloudinary_url}")
        except ValueError as e:
            logger.warning(f"Failed to extract public_id from URL: {str(e)}")
        
        # Delete from Cloudinary (if public_id was extracted)
        if cloudinary_public_id:
            try:
                result = await delete_image(cloudinary_public_id)
                logger.info(f"Successfully deleted from Cloudinary: {cloudinary_public_id}, result: {result}")
            except Exception as e:
                logger.error(f"Failed to delete from Cloudinary for image ID {image.id} (public_id: {cloudinary_public_id}): {str(e)}", exc_info=True)
                # Continue with database deletion even if Cloudinary deletion fails
                # But log the error for debugging
        
        # Delete from database
        await db.delete(image)
        logger.info(f"Successfully deleted image from database: ID {image.id}")
        
    except Exception as e:
        logger.error(f"Error processing image deletion for ID {image.id}: {str(e)}")
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
        await db.delete(image)
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

