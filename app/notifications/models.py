from django.conf import settings
from django.db import models


class UserNotificationSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_settings',
    )
    email_notifications_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'UserNotificationSettings(user={self.user_id}, email_notifications_enabled={self.email_notifications_enabled})'


class TaskNotification(models.Model):
    EVENT_STARTED = 'started'
    EVENT_COMPLETED = 'completed'
    EVENT_WARNING = 'warning'
    EVENT_FAILED = 'failed'

    EVENT_CHOICES = [
        (EVENT_STARTED, 'Started'),
        (EVENT_COMPLETED, 'Completed'),
        (EVENT_WARNING, 'Warning'),
        (EVENT_FAILED, 'Failed'),
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
        ordering = ['-created_at']

    def __str__(self):
        return f"TaskNotification(user={self.user_id}, event_type={self.event_type}, is_read={self.is_read})"
