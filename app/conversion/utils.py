import os
from django.utils.text import get_valid_filename
import uuid
from django.conf import settings

from .models import FileUpload


def get_upload_dir(user_id, file_kind, persistent=False):
    """Build upload directory path segmented by storage class, user and file kind."""
    base_subdir = settings.UPLOADS_PERSISTENT_SUBDIR if persistent else settings.UPLOADS_TEMP_SUBDIR
    return os.path.join(settings.BASE_DIR, base_subdir, f"user_{user_id}", file_kind)


def upload_file(file, upload_dir=None, user_id=None, file_kind=None, persistent=False):
    if not file:
        raise ValueError("No file provided for upload.")

    if upload_dir is None:
        if user_id is None or not file_kind:
            raise ValueError("user_id and file_kind are required when upload_dir is not provided.")
        upload_dir = get_upload_dir(user_id=user_id, file_kind=file_kind, persistent=persistent)
    elif not os.path.isabs(upload_dir):
        upload_dir = os.path.join(settings.BASE_DIR, upload_dir)
    
    # Read the file content
    file_bytes = file.read()
    
    # Uploads file, creating dir and avoiding collisions
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = get_valid_filename(file.name) # Makes filename safe
    dest_path = os.path.join(upload_dir, safe_name)
    if os.path.exists(dest_path):
        base, ext = os.path.splitext(safe_name)
        dest_path = os.path.join(upload_dir, f"{base}_{uuid.uuid4().hex}{ext}")

    # Upload the file
    with open(dest_path, 'wb') as f:
        f.write(file_bytes)

    return dest_path


def delete_file_safely(path):
    """Delete a file if present, never raising errors. Returns True when deleted."""
    if not path:
        raise ValueError("No path provided for deletion.")

    os.remove(path)


def get_result_filename_stem(result_prefix, job_id):
    """Build persisted result filename stem like '<prefix>_<job_id>'."""
    return f"{result_prefix}_{job_id}"


def find_latest_persisted_upload(user_id, filename_stem):
    """Return latest persisted upload matching a filename stem, or None."""
    return FileUpload.objects.filter(
        user_id=user_id,
        file__contains=filename_stem,
    ).order_by("-uploaded_at").first()


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
