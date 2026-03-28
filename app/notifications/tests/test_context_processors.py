from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from notifications.context_processors import unread_notifications_count
from notifications.models import TaskNotification


User = get_user_model()


class NotificationContextProcessorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='user', password='pass1234', email='user@example.com')
        self.other_user = User.objects.create_user(username='other', password='pass1234', email='other@example.com')

    def test_unread_notifications_count_for_authenticated_user_cases(self):
        test_cases = [
            (0, 0, 0),
            (1, 0, 1),
            (2, 1, 2),
            (4, 3, 4),
        ]

        for unread_count, read_count, expected_unread in test_cases:
            with self.subTest(unread_count=unread_count, read_count=read_count):
                TaskNotification.objects.filter(user=self.user).delete()

                for unread_i in range(unread_count):
                    TaskNotification.objects.create(
                        user=self.user,
                        event_type=TaskNotification.EVENT_FAILED,
                        message=f'unread-{unread_i}',
                        channels=[TaskNotification.CHANNEL_IN_APP],
                        is_read=False,
                    )

                for read_i in range(read_count):
                    TaskNotification.objects.create(
                        user=self.user,
                        event_type=TaskNotification.EVENT_COMPLETED,
                        message=f'read-{read_i}',
                        channels=[TaskNotification.CHANNEL_IN_APP],
                        is_read=True,
                    )

                request = self.factory.get('/')
                request.user = self.user
                context = unread_notifications_count(request)

                self.assertEqual(context['unread_notifications_count'], expected_unread)

    def test_unread_notifications_count_does_not_include_other_users(self):
        TaskNotification.objects.create(
            user=self.user,
            event_type=TaskNotification.EVENT_FAILED,
            message='my-unread',
            channels=[TaskNotification.CHANNEL_IN_APP],
            is_read=False,
        )
        TaskNotification.objects.create(
            user=self.other_user,
            event_type=TaskNotification.EVENT_FAILED,
            message='other-unread',
            channels=[TaskNotification.CHANNEL_IN_APP],
            is_read=False,
        )

        request = self.factory.get('/')
        request.user = self.user
        context = unread_notifications_count(request)

        self.assertEqual(context['unread_notifications_count'], 1)

    def test_unread_notifications_count_for_anonymous_user(self):
        request = self.factory.get('/')
        request.user = AnonymousUser()

        context = unread_notifications_count(request)
        self.assertEqual(context['unread_notifications_count'], 0)
