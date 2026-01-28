# TODO: Implement actual notification logic (e.g., email, in-app notifications)
def notify_user(message):
    """ Notifies the user with the given message. """
    print(message)

def notify_user_annotation_complete(user, task):
    """
    Notifies user that the annotation is complete.
    """
    message = f"The annotation for the task with ID {task.external_job_id} is complete. You can now access your results."
    notify_user(message)

def notify_user_annotation_failed(user, task):
    """
    Notifies user that the annotation has failed.
    """
    message = f"The annotation for the task with ID {task.external_job_id} has failed. Please try again."
    notify_user(message)
