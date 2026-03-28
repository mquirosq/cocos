from django.contrib import admin

from notifications.models import TaskNotification


@admin.register(TaskNotification)
class TaskNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'event_type', 'is_read', 'created_at')
    list_filter = ('event_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'message')
