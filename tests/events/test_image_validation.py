"""Unit tests for events.image_validation.validate_uploaded_image.

Covers the reject branches (size, extension allowlist, undecodable content,
spoofed format, oversized dimensions) that the upload-API tests don't reach,
plus the EXIF-stripping re-encode step on the accept path.
"""
import io

import PIL.Image
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import ExifTags
from rest_framework import serializers

from events.image_validation import (
    MAX_IMAGE_DIMENSION_PX,
    MAX_IMAGE_SIZE_BYTES,
    validate_uploaded_image,
)

pytestmark = pytest.mark.unit


def _img_bytes(fmt="PNG", size=(10, 10), color=(255, 0, 0)):
    buf = io.BytesIO()
    PIL.Image.new("RGB", size, color=color).save(buf, format=fmt)
    return buf.getvalue()


def _jpeg_bytes_with_gps_exif(size=(30, 10), color=(255, 0, 0), orientation=6):
    """A JPEG carrying GPS EXIF and an orientation tag, built with Pillow
    alone (no piexif dependency) via Image.getexif()."""
    img = PIL.Image.new("RGB", size, color=color)
    exif = img.getexif()
    exif[ExifTags.Base.GPSInfo] = {1: "N", 2: (37.0, 33.0, 2.5), 3: "E", 4: (127.0, 0.0, 4.2)}
    exif[ExifTags.Base.Orientation] = orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _upload(content, name="photo.png", content_type="image/png"):
    return SimpleUploadedFile(name, content, content_type=content_type)


class TestValidImage:
    def test_유효한_PNG는_형식과_크기를_유지한_채_통과한다(self):
        # The accept path now re-encodes to strip metadata, so the returned
        # file is a new object — assert it decodes back to the same format/
        # size rather than asserting object identity.
        value = _upload(_img_bytes("PNG", size=(10, 10)), name="ok.png")

        result = validate_uploaded_image(value)
        result.seek(0)
        reopened = PIL.Image.open(result)
        assert reopened.format == "PNG"
        assert reopened.size == (10, 10)


class TestExifStripping:
    def test_업로드한_JPEG의_GPS_EXIF_정보는_제거된다(self):
        value = _upload(
            _jpeg_bytes_with_gps_exif(), name="photo.jpg", content_type="image/jpeg"
        )

        result = validate_uploaded_image(value)
        result.seek(0)
        reopened = PIL.Image.open(result)
        result_exif = reopened.getexif()

        assert ExifTags.Base.GPSInfo not in result_exif
        assert not result_exif.get_ifd(ExifTags.IFD.GPSInfo)

    def test_EXIF_방향_태그는_픽셀_회전으로_반영되고_태그_자체는_남지_않는다(self):
        # orientation=6 ("rotate 90") on a 30x10 source must land as a
        # 10x30 image with no orientation tag left for a naive viewer to
        # apply a second time.
        value = _upload(
            _jpeg_bytes_with_gps_exif(size=(30, 10), orientation=6),
            name="portrait.jpg",
            content_type="image/jpeg",
        )

        result = validate_uploaded_image(value)
        result.seek(0)
        reopened = PIL.Image.open(result)

        assert reopened.size == (10, 30)
        assert ExifTags.Base.Orientation not in reopened.getexif()


class TestRejections:
    def test_최대_크기를_초과한_파일은_업로드가_거부된다(self):
        big = b"\x89PNG\r\n" + b"0" * (MAX_IMAGE_SIZE_BYTES + 1)
        value = _upload(big, name="big.png")
        with pytest.raises(serializers.ValidationError):
            validate_uploaded_image(value)

    @pytest.mark.parametrize(
        "name",
        ["evil.svg", "sneaky.gif", "noext"],
        ids=["svg_확장자", "gif_확장자", "확장자_없음"],
    )
    def test_허용되지_않은_확장자는_업로드가_거부된다(self, name):
        value = _upload(_img_bytes("PNG"), name=name)
        with pytest.raises(serializers.ValidationError):
            validate_uploaded_image(value)

    def test_이미지가_아닌_내용은_업로드가_거부된다(self):
        value = _upload(b"this is definitely not an image", name="fake.png")
        with pytest.raises(serializers.ValidationError):
            validate_uploaded_image(value)

    def test_허용된_확장자로_위장한_다른_형식_이미지는_업로드가_거부된다(self):
        # Real GIF bytes behind a .png name: extension passes, decoded format
        # (GIF) is not in the allowlist → rejected.
        value = _upload(_img_bytes("GIF"), name="spoof.png")
        with pytest.raises(serializers.ValidationError):
            validate_uploaded_image(value)

    def test_한_축_크기가_최대_치수를_초과한_이미지는_업로드가_거부된다(self):
        # Over the per-axis cap but well under the pixel-bomb limit so it decodes.
        wide = _img_bytes("PNG", size=(MAX_IMAGE_DIMENSION_PX + 1, 10))
        value = _upload(wide, name="wide.png")
        with pytest.raises(serializers.ValidationError):
            validate_uploaded_image(value)

    def test_두번째_이미지_열기가_실패하면_치수_오류로_거부된다(self, monkeypatch):
        # The image passes verify() but the second open (to read dimensions)
        # fails — a corruption/TOCTOU guard. Simulate by failing the 2nd open.
        import unittest.mock

        calls = {"n": 0}
        real_open = PIL.Image.open

        def flaky_open(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                stub = unittest.mock.Mock()
                stub.verify = lambda: None
                return stub
            raise OSError("re-open failed")

        monkeypatch.setattr(PIL.Image, "open", flaky_open)
        value = _upload(_img_bytes("PNG"), name="ok.png")

        with pytest.raises(serializers.ValidationError):
            validate_uploaded_image(value)
        assert calls["n"] == 2  # confirms the second-open path was taken
        assert real_open is not PIL.Image.open  # monkeypatch active
