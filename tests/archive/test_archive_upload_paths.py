"""이미지 업로드 경로 계약 — 사용자 간 파일명 충돌 덮어쓰기와 원본
파일명(개인정보) 노출을 막기 위해, 업로드 경로는 디렉터리를 유지하되
파일명은 원본을 버리고 무작위(UUID)로 새로 만들어야 한다.
"""
import uuid

import pytest

from archive.models import CollectionItem, PersonalEntry, VisitRecordPhoto

pytestmark = pytest.mark.domain


@pytest.mark.parametrize(
    "model, field_name, expected_dir",
    [
        (PersonalEntry, "image", "personal-entries"),
        (VisitRecordPhoto, "image", "visit-record-photos"),
        (CollectionItem, "image", "collection-items"),
    ],
    ids=["개인_항목", "다녀온_기록_사진", "컬렉션_아이템"],
)
def test_이미지_업로드_경로는_디렉터리를_유지하고_원본_파일명_없이_무작위_파일명을_만든다(
    model, field_name, expected_dir
):
    field = model._meta.get_field(field_name)

    result = field.upload_to(None, "원본 파일명.PNG")

    assert result.startswith(f"{expected_dir}/")
    assert result.endswith(".png")
    assert "원본" not in result
    stem = result.removeprefix(f"{expected_dir}/").removesuffix(".png")
    uuid.UUID(stem)
