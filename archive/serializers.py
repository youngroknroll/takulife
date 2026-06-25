import PIL.Image
from PIL import UnidentifiedImageError
from rest_framework import serializers

from events.models import Event

from .models import EventInterest, UserEventStatus, VisitRecord, VisitRecordPhoto


MAX_PHOTO_SIZE_BYTES = 5 * 1024 * 1024
MAX_PHOTOS_PER_RECORD = 10
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


class EventInterestSerializer(serializers.ModelSerializer):
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.published(),
    )

    class Meta:
        model = EventInterest
        fields = ["id", "event"]
        read_only_fields = ["id"]


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

        value.seek(0)
        return value
