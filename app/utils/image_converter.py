"""
Image conversion utility for converting images to WebP format.
Reduces file size before uploading to Cloudinary.
"""
import io
import logging
from typing import Optional, Tuple
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

# WebP conversion settings
DEFAULT_WEBP_QUALITY = 85  # Balance between quality and file size (0-100)
DEFAULT_WEBP_METHOD = 6    # Compression method (0-6, higher = better compression but slower)
MAX_DIMENSION = 3840       # Maximum width or height before downscaling (optional, None to disable)


async def convert_to_webp(
    image_bytes: bytes,
    quality: int = DEFAULT_WEBP_QUALITY,
    method: int = DEFAULT_WEBP_METHOD,
    max_dimension: Optional[int] = MAX_DIMENSION,
    skip_if_webp: bool = True
) -> Tuple[bytes, bool]:
    """
    Convert image bytes to WebP format to reduce file size.
    
    Args:
        image_bytes: Original image file bytes
        quality: WebP quality (0-100, default: 85)
        method: WebP compression method (0-6, default: 6)
        max_dimension: Maximum width or height before downscaling (None to disable)
        skip_if_webp: If True, return original bytes if already WebP format
    
    Returns:
        Tuple[bytes, bool]: 
            - Converted image bytes (or original if skipped/failed)
            - Whether conversion was successful/skipped (True) or failed (False)
    
    Raises:
        UnidentifiedImageError: If image format cannot be identified
        Exception: For other image processing errors
    """
    try:
        # Open image from bytes
        image = Image.open(io.BytesIO(image_bytes))
        
        # Check if already WebP format
        if skip_if_webp and image.format == 'WEBP':
            logger.debug("Image is already WebP format, skipping conversion")
            return image_bytes, True
        
        # Handle RGBA mode (for PNG with transparency)
        # WebP supports transparency, so preserve alpha channel
        if image.mode in ('RGBA', 'LA', 'P'):
            # Preserve transparency
            if image.mode == 'P':
                image = image.convert('RGBA')
            # Keep RGBA/LA as is
        elif image.mode not in ('RGB', 'RGBA'):
            # Convert other modes (CMYK, LAB, etc.) to RGB
            if image.mode == 'CMYK':
                image = image.convert('RGB')
            elif image.mode == 'L':  # Grayscale
                image = image.convert('RGB')
            else:
                # Fallback: convert to RGB
                logger.warning(f"Unusual image mode '{image.mode}', converting to RGB")
                image = image.convert('RGB')
        
        # Optional: Downscale if image exceeds max_dimension
        if max_dimension:
            width, height = image.size
            if width > max_dimension or height > max_dimension:
                # Calculate new dimensions maintaining aspect ratio
                if width > height:
                    new_width = max_dimension
                    new_height = int(height * (max_dimension / width))
                else:
                    new_height = max_dimension
                    new_width = int(width * (max_dimension / height))
                
                logger.info(
                    f"Downscaling image from {width}x{height} to {new_width}x{new_height} "
                    f"(max dimension: {max_dimension})"
                )
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Convert to WebP
        webp_buffer = io.BytesIO()
        
        # Save with WebP settings
        save_kwargs = {
            'format': 'WEBP',
            'quality': quality,
            'method': method,
        }
        
        # Preserve lossless mode for very small images or if quality is 100
        if quality == 100:
            save_kwargs['lossless'] = True
            logger.debug("Using lossless WebP compression")
        
        image.save(webp_buffer, **save_kwargs)
        webp_bytes = webp_buffer.getvalue()
        
        original_size = len(image_bytes)
        converted_size = len(webp_bytes)
        reduction = ((original_size - converted_size) / original_size) * 100
        
        logger.info(
            f"Successfully converted image to WebP: "
            f"{original_size:,} bytes → {converted_size:,} bytes "
            f"({reduction:.1f}% reduction, quality={quality})"
        )
        
        return webp_bytes, True
        
    except UnidentifiedImageError as e:
        logger.warning(f"Cannot identify image format: {str(e)}")
        return image_bytes, False
    
    except Exception as e:
        logger.error(f"Error converting image to WebP: {str(e)}", exc_info=True)
        return image_bytes, False


def is_webp_format(image_bytes: bytes) -> bool:
    """
    Check if image bytes are already in WebP format.
    
    Args:
        image_bytes: Image file bytes
    
    Returns:
        bool: True if image is WebP format, False otherwise
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        return image.format == 'WEBP'
    except Exception:
        return False


def get_image_info(image_bytes: bytes) -> Optional[dict]:
    """
    Get basic information about an image.
    
    Args:
        image_bytes: Image file bytes
    
    Returns:
        dict: Image information (format, size, mode) or None if error
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        return {
            'format': image.format,
            'size': image.size,
            'mode': image.mode,
            'bytes': len(image_bytes)
        }
    except Exception as e:
        logger.debug(f"Error getting image info: {str(e)}")
        return None

