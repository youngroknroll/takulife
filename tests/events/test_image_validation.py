"""events.image_validation.validate_uploaded_image에 대한 단위 테스트.

업로드 API 테스트가 닿지 않는 거부 분기(크기, 확장자 허용목록, 디코드
불가 내용, 위장 형식, 초과 치수)와, 통과 시의 EXIF 제거 재인코딩 단계를
다룬다.
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
    """GPS EXIF와 방향 태그를 담은 JPEG을 piexif 없이 Pillow의
    Image.getexif()만으로 만든다."""
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
        # 통과 경로는 메타데이터 제거를 위해 재인코딩하므로 반환 파일은 새
        # 객체다 — 객체 동일성이 아니라 디코드했을 때 형식/크기가 같은지로 검증한다.
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
        # orientation=6("90도 회전")을 가진 30x10 원본은 10x30 이미지로
        # 바뀌어야 하고, 방향 태그가 남아 다른 뷰어가 다시 회전시키면 안 된다.
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
        # .png 이름 뒤에 실제 GIF 바이트가 있는 경우: 확장자는 통과하지만
        # 디코드된 형식(GIF)이 허용목록에 없어 거부된다.
        value = _upload(_img_bytes("GIF"), name="spoof.png")
        with pytest.raises(serializers.ValidationError):
            validate_uploaded_image(value)

    def test_한_축_크기가_최대_치수를_초과한_이미지는_업로드가_거부된다(self):
        # 축별 상한은 넘지만 픽셀-폭탄 한도보다는 훨씬 작아 디코드는 된다.
        wide = _img_bytes("PNG", size=(MAX_IMAGE_DIMENSION_PX + 1, 10))
        value = _upload(wide, name="wide.png")
        with pytest.raises(serializers.ValidationError):
            validate_uploaded_image(value)

    def test_두번째_이미지_열기가_실패하면_치수_오류로_거부된다(self, monkeypatch):
        # verify()는 통과하지만 치수를 읽기 위한 두 번째 open이 실패하는
        # 경우다 — 손상/TOCTOU 가드. 두 번째 open만 실패하도록 흉내낸다.
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
        assert calls["n"] == 2
        assert real_open is not PIL.Image.open
