# TODO: Implement actual notification logic (e.g., email, in-app notifications)
# TODO: Add users to the notification functions when user management is implemented
def notify_user(user, message):
    """ Notifies the user with the given message. """
    print(message)

def notify_user_conversion_complete(user, task):
    """
    Notifies user that the conversion is complete.
    """
    message = f"The conversion for the task with ID {task.external_job_id} is complete. You can now access your results."
    notify_user(user, message)

def notify_user_conversion_failed(user, task):
    """
    Notifies user that the conversion has failed.
    """
    message = f"The conversion for the task with ID {task.external_job_id} has failed. Please try again."
    notify_user(user, message)

def notify_user_server_busy(user):
    """
    Notifies user that the server is busy and the task could not be started.
    """
    message = "The conversion server is currently at maximum capacity. Please try again later."
    notify_user(user, message)
