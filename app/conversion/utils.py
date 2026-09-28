from .models import ConversionTask

def get_result_filename_stem(result_prefix, job_id):
    """Build a consistent filename stem for a bio-service result."""
    return f"{result_prefix}_{job_id}"

def get_current_user_tasks(request):
    """Return tasks filtered by authenticated user."""
    return ConversionTask.objects.filter(process__user=request.user)
