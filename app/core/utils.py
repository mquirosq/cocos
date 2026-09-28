from core.models import File

def upload_file(file, user, file_type):
    """Upload a file to the system, associating it with a user and file type."""
    if not file:
        raise ValueError("No file provided for upload.")

    file_obj = File(user=user, file_type=file_type)

    file_obj.file.save(file.name, file, save=True)

    return file_obj