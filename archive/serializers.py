import PIL.Image
from rest_framework import serializers

from events.models import Event

from .models import UserEventStatus, VisitRecord, VisitRecordPhoto


MAX_PHOTO_SIZE_BYTES = 5 * 1024 * 1024
MAX_PHOTOS_PER_RECORD = 10
# Maximum pixel dimension per axis (decompression-bomb guard)
MAX_IMAGE_DIMENSION_PX = 10_000
# Allowed file extensions (lower-cased, without dot)
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


class UserEventStatusSerializer(serializers.ModelSerializer):
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.published(),
    )

    class Meta:
        model = UserEventStatus
        fields = ["id", "event", "status"]
        read_only_fields = ["id"]


class UserEventStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserEventStatus
        fields = ["id", "event", "status"]
        read_only_fields = ["id", "event"]


class UserEventStatusQuerySerializer(serializers.Serializer):
    event = serializers.IntegerField(required=False)
    status = serializers.ChoiceField(required=False, choices=UserEventStatus.Status.choices)


class VisitRecordSerializer(serializers.ModelSerializer):
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.published(),
    )

    class Meta:
        model = VisitRecord
        fields = ["id", "event", "visited_on", "short_review"]
        read_only_fields = ["id"]


class VisitRecordPhotoUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)

    def validate_image(self, value):
        # 1. File size check (max 5 MB)
        if value.size > MAX_PHOTO_SIZE_BYTES:
            raise serializers.ValidationError(
                f"Image file is too large. Maximum allowed size is {MAX_PHOTO_SIZE_BYTES // (1024 * 1024)} MB."
            )

        # 2. Extension allowlist: reject SVG and anything not in jpg/jpeg/png/webp
        name = getattr(value, "name", "") or ""
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                "Unsupported file extension. Allowed: jpg, jpeg, png, webp."
            )

        # 3. Real content inspection via Pillow (ImageField already calls PIL.Image.open;
        #    we additionally run verify() and check decompression-bomb dimensions).
        value.seek(0)
        try:
            img = PIL.Image.open(value)
            img.verify()
        except Exception:
            raise serializers.ValidationError("File does not appear to be a valid image.")

        # 4. Decompression-bomb guard: cap pixel dimensions
        value.seek(0)
        try:
            img2 = PIL.Image.open(value)
            width, height = img2.size
        except Exception:
            raise serializers.ValidationError("Could not read image dimensions.")

        if width > MAX_IMAGE_DIMENSION_PX or height > MAX_IMAGE_DIMENSION_PX:
            raise serializers.ValidationError(
                f"Image dimensions exceed maximum allowed size of {MAX_IMAGE_DIMENSION_PX}px per axis."
            )

        value.seek(0)
        return value
