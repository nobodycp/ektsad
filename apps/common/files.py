from django.core.exceptions import ValidationError


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
DOCUMENT_TYPES = IMAGE_TYPES | {"application/pdf"}


def validate_upload(uploaded, *, kinds: set[str]):
    allowed = set()
    if "image" in kinds:
        allowed |= IMAGE_TYPES
    if "document" in kinds:
        allowed |= DOCUMENT_TYPES
    if uploaded.size > MAX_UPLOAD_BYTES or uploaded.content_type not in allowed:
        raise ValidationError("الملف غير صالح.")
