"""이미지 업로드 검증 공용 로직.

이 모듈은 최하위 모듈이라 events.models 등 다른 앱 모델을 임포트하면 안 된다.
그래야 archive와 events의 serializer가 순환 임포트 없이 이 모듈을 함께 쓸 수 있다.
"""

import io

import PIL.Image
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import ImageOps, UnidentifiedImageError
from rest_framework import serializers


MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
# 압축폭탄 방어: 한 축의 최대 픽셀 길이
MAX_IMAGE_DIMENSION_PX = 10_000
# 압축폭탄 방어: 축 길이 제한만으로는 디코딩 후 메모리 사용량을 못 막아 전체 픽셀 수도 따로 제한한다.
MAX_IMAGE_PIXELS_LIMIT = 40_000_000
# 허용 확장자 (소문자, 점 없이)
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
# 확장자는 사용자가 임의로 붙일 수 있으므로, 실제로 신뢰하는 허용 목록은 Pillow가 디코딩한 포맷 쪽이다.
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
# 여기 나열된 것만 "이미지 아님"으로 처리하고, 그 외 예외는 실제 오류로 그대로 전파한다.
_PIL_DECODE_ERRORS = (OSError, UnidentifiedImageError, PIL.Image.DecompressionBombError)
# 손실 포맷(JPEG/WEBP) 재인코딩 화질 — 육안으로 티 나지 않는 수준. PNG는 무손실이라 화질 옵션이 없다.
_REENCODE_QUALITY = 95
_FORMAT_CONTENT_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def _strip_exif_metadata(image, image_format):
    """디코딩된 이미지를 EXIF 없이 다시 인코딩한다.

    exif_transpose()로 방향 태그를 픽셀에 먼저 반영해야 태그 삭제 후에도
    세로 사진이 옆으로 눕지 않는다. Pillow는 exif= 인자를 안 주면 저장 시
    EXIF를 넣지 않으므로, 이 재저장만으로 GPS 등 원본 메타데이터가 전부 빠진다.
    """
    normalized = ImageOps.exif_transpose(image)
    if image_format == "JPEG" and normalized.mode not in ("RGB", "L"):
        # JPEG는 알파 채널이 없어 인코딩 전에 미리 제거한다.
        normalized = normalized.convert("RGB")
    save_kwargs = {"quality": _REENCODE_QUALITY} if image_format in ("JPEG", "WEBP") else {}
    buffer = io.BytesIO()
    normalized.save(buffer, format=image_format, **save_kwargs)
    buffer.seek(0)
    return buffer


def validate_uploaded_image(value):
    """업로드 이미지를 검증하고, 통과하면 메타데이터를 지운 새 파일 객체를 돌려준다.

    반환값은 원본 value가 아니라 재인코딩된 새 파일이므로, 호출부는 반드시
    반환값을 저장해야 한다.
    """
    if value.size > MAX_IMAGE_SIZE_BYTES:
        raise serializers.ValidationError(
            f"Image file is too large. Maximum allowed size is {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB."
        )

    name = getattr(value, "name", "") or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise serializers.ValidationError(
            "Unsupported file extension. Allowed: jpg, jpeg, png, webp."
        )

    # ImageField가 이미 PIL.Image.open을 호출하지만, verify()로 진짜 이미지인지 한 번 더 확인한다.
    value.seek(0)
    try:
        img = PIL.Image.open(value)
        img.verify()
    except _PIL_DECODE_ERRORS:
        raise serializers.ValidationError("File does not appear to be a valid image.")

    # verify() 이후에는 이미지 객체를 다시 못 쓰므로 재오픈해서 포맷과 크기를 읽는다.
    value.seek(0)
    try:
        img2 = PIL.Image.open(value)
        image_format = img2.format
        width, height = img2.size
    except _PIL_DECODE_ERRORS:
        raise serializers.ValidationError("Could not read image dimensions.")

    # 허용 확장자로 위장한 다른 포맷 파일을 걸러낸다.
    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise serializers.ValidationError(
            "Unsupported image format. Allowed: JPEG, PNG, WEBP."
        )

    if width > MAX_IMAGE_DIMENSION_PX or height > MAX_IMAGE_DIMENSION_PX:
        raise serializers.ValidationError(
            f"Image dimensions exceed maximum allowed size of {MAX_IMAGE_DIMENSION_PX}px per axis."
        )

    if width * height > MAX_IMAGE_PIXELS_LIMIT:
        raise serializers.ValidationError(
            f"Image is too large to process. Maximum total area is {MAX_IMAGE_PIXELS_LIMIT} pixels."
        )

    buffer = _strip_exif_metadata(img2, image_format)
    return InMemoryUploadedFile(
        buffer,
        field_name=getattr(value, "field_name", None),
        name=name,
        content_type=_FORMAT_CONTENT_TYPES[image_format],
        size=buffer.getbuffer().nbytes,
        charset=None,
    )
