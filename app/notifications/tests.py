from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from conversion.models import ConversionTask
from notifications.models import TaskNotification
from notifications.services import notify_user_conversion_failed


User = get_user_model()


class NotificationFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pass1234', email='alice@example.com')
        self.other_user = User.objects.create_user(username='bob', password='pass1234', email='bob@example.com')
        self.client = Client()
        self.client.login(username='alice', password='pass1234')

        self.task = ConversionTask.objects.create(
            external_job_id='job-1',
            status='running',
            input_path='uploads/persistent/user_1/fasta/demo.fasta',
            task_type='annotation',
            user=self.user,
        )

    def test_notify_user_conversion_failed_persists_notification(self):
        notify_user_conversion_failed(self.user, self.task, message='custom failure')
        notification = TaskNotification.objects.get(user=self.user)
        self.assertEqual(notification.event_type, TaskNotification.EVENT_FAILED)
        self.assertEqual(notification.message, 'custom failure')
        self.assertFalse(notification.is_read)

    def test_notifications_page_requires_auth_and_is_scoped(self):
        TaskNotification.objects.create(
            user=self.user,
            task=self.task,
            event_type=TaskNotification.EVENT_COMPLETED,
            message='done',
            channels=[TaskNotification.CHANNEL_IN_APP],
        )
        TaskNotification.objects.create(
            user=self.other_user,
            event_type=TaskNotification.EVENT_FAILED,
            message='private',
            channels=[TaskNotification.CHANNEL_IN_APP],
        )

        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        rendered_notifications = list(response.context['notifications'])
        self.assertEqual(len(rendered_notifications), 1)
        self.assertEqual(rendered_notifications[0].user_id, self.user.id)

    def test_mark_notification_read_only_for_owner(self):
        own_notification = TaskNotification.objects.create(
            user=self.user,
            task=self.task,
            event_type=TaskNotification.EVENT_COMPLETED,
            message='done',
            channels=[TaskNotification.CHANNEL_IN_APP],
        )
        foreign_notification = TaskNotification.objects.create(
            user=self.other_user,
            event_type=TaskNotification.EVENT_FAILED,
            message='private',
            channels=[TaskNotification.CHANNEL_IN_APP],
        )

        mark_url = reverse('notifications:mark_read', kwargs={'notification_id': own_notification.id})
        response = self.client.post(mark_url)
        self.assertEqual(response.status_code, 302)
        own_notification.refresh_from_db()
        self.assertTrue(own_notification.is_read)

        foreign_mark_url = reverse('notifications:mark_read', kwargs={'notification_id': foreign_notification.id})
        foreign_response = self.client.post(foreign_mark_url)
        self.assertEqual(foreign_response.status_code, 404)
