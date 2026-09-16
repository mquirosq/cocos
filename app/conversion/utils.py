import os
from django.utils.text import get_valid_filename
import uuid
from django.conf import settings

from .models import File


def get_primary_input_path(path_value):
    """Return first comma-separated input path segment, stripped."""
    return (path_value or "").split(",")[0].strip()


def resolve_absolute_path(path_value):
    """Resolve a path to absolute form, using BASE_DIR for relative paths."""
    if not path_value:
        return None
    if os.path.isabs(path_value):
        return os.path.abspath(path_value)
    return os.path.abspath(os.path.join(settings.BASE_DIR, path_value))

def upload_file(file, user, file_kind):
    if not file:
        raise ValueError("No file provided for upload.")

    file_obj = File(user=user, file_type=file_kind)

    file_obj.file.save(file.name, file, save=True)

    return file_obj

def get_result_filename_stem(result_prefix, job_id):
    """Build persisted result filename stem like '<prefix>_<job_id>'."""
    return f"{result_prefix}_{job_id}"


def find_latest_persisted_upload(user_id, filename_stem):
    """Return latest persisted upload matching a filename stem, or None."""
    return File.objects.filter(
        user_id=user_id,
        file__contains=filename_stem,
    ).order_by("-created_at").first()


def resolve_persisted_result_filename(user_id, result_prefix, job_id):
    """Resolve persisted filename for a job result, returning None when unavailable."""
    if not job_id:
        return None

    filename_stem = get_result_filename_stem(result_prefix, job_id)
    persisted_upload = find_latest_persisted_upload(user_id=user_id, filename_stem=filename_stem)
    if persisted_upload and persisted_upload.file:
        return os.path.basename(persisted_upload.file.name)

    return None


def read_persisted_upload_bytes(user_id, filename_stem):
    """Read bytes from latest persisted upload matching a filename stem."""
    persisted_upload = find_latest_persisted_upload(user_id=user_id, filename_stem=filename_stem)
    if not persisted_upload:
        return None
    with persisted_upload.file.open("rb") as persisted_file:
        return persisted_file.read()
