from django.conf import settings
from django.db import models


class TaskNotification(models.Model):
    EVENT_STARTED = 'started'
    EVENT_COMPLETED = 'completed'
    EVENT_FAILED = 'failed'
    EVENT_SERVER_BUSY = 'server_busy'

    EVENT_CHOICES = [
        (EVENT_STARTED, 'Started'),
        (EVENT_COMPLETED, 'Completed'),
        (EVENT_FAILED, 'Failed'),
        (EVENT_SERVER_BUSY, 'Server Busy'),
    ]

    CHANNEL_IN_APP = 'in_app'
    CHANNEL_EMAIL = 'email'
    CHANNEL_CHOICES = [
        (CHANNEL_IN_APP, 'In-app'),
        (CHANNEL_EMAIL, 'Email'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='task_notifications')
    task = models.ForeignKey('conversion.ConversionTask', on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    channels = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'converter_tasknotification'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f"TaskNotification(user={self.user_id}, event_type={self.event_type}, is_read={self.is_read})"
