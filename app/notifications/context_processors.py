from notifications.models import TaskNotification


def unread_notifications_count(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {'unread_notifications_count': 0}

    count = TaskNotification.objects.filter(user=request.user, is_read=False).count()
    return {'unread_notifications_count': count}
