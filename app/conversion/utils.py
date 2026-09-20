from .models import ConversionTask, File

def upload_file(file, user, file_type):
    """Upload a file to the system, associating it with a user and file type."""
    if not file:
        raise ValueError("No file provided for upload.")

    file_obj = File(user=user, file_type=file_type)

    file_obj.file.save(file.name, file, save=True)

    return file_obj

def get_result_filename_stem(result_prefix, job_id):
    """Build a consistent filename stem for a bio-service result."""
    return f"{result_prefix}_{job_id}"

def get_current_user_tasks(request):
    """Return tasks filtered by authenticated user."""
    return ConversionTask.objects.filter(process__user=request.user)
