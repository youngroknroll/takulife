"""
Shared image validation logic for uploaded image files.

This module is a leaf module: it must NOT import events.models or any other
app model. It may be imported by archive and events serializers without
creating import cycles.
"""

import io

import PIL.Image
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import ImageOps, UnidentifiedImageError
from rest_framework import serializers


MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
# Maximum pixel dimension per axis (decompression-bomb guard)
MAX_IMAGE_DIMENSION_PX = 10_000
# Maximum total decoded pixel area (decompression-bomb guard; the byte and
# per-axis caps do not bound the decoded memory footprint on their own).
MAX_IMAGE_PIXELS_LIMIT = 40_000_000
# Allowed file extensions (lower-cased, without dot)
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
# Allowed real Pillow-decoded formats. The extension is attacker-controlled, so
# the decoded format is the authoritative allowlist.
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
# Concrete Pillow decode failures — anything else propagates as a real error
# instead of being masked as "invalid image".
_PIL_DECODE_ERRORS = (OSError, UnidentifiedImageError, PIL.Image.DecompressionBombError)
# Re-encode quality for lossy formats (JPEG/WEBP re-save below) — high enough
# that a second compression pass is not visually noticeable; PNG is lossless
# so it takes no quality kwarg.
_REENCODE_QUALITY = 95
_FORMAT_CONTENT_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def _strip_exif_metadata(image, image_format):
    """Re-encode a decoded Pillow image without carrying its EXIF forward.

    ImageOps.exif_transpose() bakes any EXIF orientation into the pixel data
    first, so a photo shot in portrait doesn't end up sideways once the
    orientation tag is dropped. Pillow's Image.save() only embeds an EXIF
    payload when one is explicitly passed via ``exif=``, so a plain re-save
    (no such kwarg) discards whatever metadata — including GPS — the source
    file carried, without needing to touch tags one by one.
    """
    normalized = ImageOps.exif_transpose(image)
    if image_format == "JPEG" and normalized.mode not in ("RGB", "L"):
        # JPEG has no alpha channel; drop it before encoding.
        normalized = normalized.convert("RGB")
    save_kwargs = {"quality": _REENCODE_QUALITY} if image_format in ("JPEG", "WEBP") else {}
    buffer = io.BytesIO()
    normalized.save(buffer, format=image_format, **save_kwargs)
    buffer.seek(0)
    return buffer


def validate_uploaded_image(value):
    """Validate an uploaded image file.

    Raises serializers.ValidationError if the file fails any check.
    On success, returns a NEW file object — a metadata-stripped re-encode of
    the input, not the original ``value`` — so callers must save the
    returned file, not the argument.

    Checks performed (in order):
    1. File size cap (MAX_IMAGE_SIZE_BYTES)
    2. Extension allowlist (jpg/jpeg/png/webp)
    3. Pillow verify() — confirms the file is a real image
    4. Decoded format allowlist (JPEG/PNG/WEBP)
    5. Per-axis dimension cap (MAX_IMAGE_DIMENSION_PX)
    6. Total pixel-area cap (MAX_IMAGE_PIXELS_LIMIT)
    7. EXIF/GPS metadata strip (re-encode, see _strip_exif_metadata)
    """
    # 1. File size check (max 5 MB)
    if value.size > MAX_IMAGE_SIZE_BYTES:
        raise serializers.ValidationError(
            f"Image file is too large. Maximum allowed size is {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB."
        )

    # 2. Extension allowlist: reject SVG and anything not in jpg/jpeg/png/webp
    name = getattr(value, "name", "") or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise serializers.ValidationError(
            "Unsupported file extension. Allowed: jpg, jpeg, png, webp."
        )

    # 3. Real content inspection via Pillow (ImageField already calls PIL.Image.open;
    #    we additionally run verify() and check the decoded format/dimensions).
    value.seek(0)
    try:
        img = PIL.Image.open(value)
        img.verify()
    except _PIL_DECODE_ERRORS:
        raise serializers.ValidationError("File does not appear to be a valid image.")

    # verify() leaves the image object unusable, so re-open to read the
    # authoritative decoded format and dimensions.
    value.seek(0)
    try:
        img2 = PIL.Image.open(value)
        image_format = img2.format
        width, height = img2.size
    except _PIL_DECODE_ERRORS:
        raise serializers.ValidationError("Could not read image dimensions.")

    # 4. Format allowlist on the real decoded format (defends against an image
    #    in a disallowed format spoofed with an allowed extension).
    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise serializers.ValidationError(
            "Unsupported image format. Allowed: JPEG, PNG, WEBP."
        )

    # 5. Decompression-bomb guard: cap both per-axis dimensions and total area.
    if width > MAX_IMAGE_DIMENSION_PX or height > MAX_IMAGE_DIMENSION_PX:
        raise serializers.ValidationError(
            f"Image dimensions exceed maximum allowed size of {MAX_IMAGE_DIMENSION_PX}px per axis."
        )

    if width * height > MAX_IMAGE_PIXELS_LIMIT:
        raise serializers.ValidationError(
            f"Image is too large to process. Maximum total area is {MAX_IMAGE_PIXELS_LIMIT} pixels."
        )

    # 6. Strip EXIF/GPS metadata: re-encode through Pillow so nothing the
    #    original file carried (location, camera, orientation as a tag)
    #    survives into storage.
    buffer = _strip_exif_metadata(img2, image_format)
    return InMemoryUploadedFile(
        buffer,
        field_name=getattr(value, "field_name", None),
        name=name,
        content_type=_FORMAT_CONTENT_TYPES[image_format],
        size=buffer.getbuffer().nbytes,
        charset=None,
    )
