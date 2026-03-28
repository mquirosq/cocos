from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from notifications.models import TaskNotification


def _get_current_user_notifications(request):
    return TaskNotification.objects.filter(user=request.user)


@login_required
def notifications_view(request):
    status_filter = request.GET.get('status', 'all')
    notifications = _get_current_user_notifications(request)
    if status_filter == 'read':
        notifications = notifications.filter(is_read=True)
    elif status_filter == 'unread':
        notifications = notifications.filter(is_read=False)

    context = {
        'notifications': notifications.order_by('-created_at'),
        'status_filter': status_filter,
    }
    return render(request, 'model/notifications.html', context)


@login_required
@require_POST
def mark_notification_read_view(request, notification_id):
    notification = get_object_or_404(_get_current_user_notifications(request), id=notification_id)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    return redirect(request.POST.get('next') or 'notifications:list')


@login_required
@require_POST
def mark_all_notifications_read_view(request):
    _get_current_user_notifications(request).filter(is_read=False).update(is_read=True)
    return redirect(request.POST.get('next') or 'notifications:list')
