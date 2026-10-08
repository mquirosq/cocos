from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import ProcessGroup
from core.testing import FakeBioService, FlowTestMixin
from notifications.models import TaskNotification


class NotificationViewsTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        with FakeBioService():
            self.client.post(reverse('conversion:assembly_run'), data={
                'assembly_type': 'ont',
                'fastq_file': SimpleUploadedFile('reads.fastq.gz', b'READS'),
            })
        self.process = ProcessGroup.objects.get(user=self.user)
        self.mine = TaskNotification.objects.filter(user=self.user)

    def test_conversion_creates_started_and_completed_notifications_linked_to_process(self):
        events = set(self.mine.values_list('event_type', flat=True))
        self.assertTrue({TaskNotification.EVENT_STARTED, TaskNotification.EVENT_COMPLETED} <= events)
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('conversion:process_status', args=[self.process.id]))
        self.assertTrue(any('reads.fastq.gz' in n.message for n in self.mine))

    def test_filters_and_partial_panel(self):
        first = self.mine.order_by('id').first()
        self.client.post(reverse('notifications:mark_read', args=[first.id]))

        unread = self.client.get(reverse('notifications:list'), {'status': 'unread'}).context['notifications']
        read = self.client.get(reverse('notifications:list'), {'status': 'read'}).context['notifications']
        self.assertNotIn(first, list(unread))
        self.assertEqual(list(read), [first])

        partial = self.client.get(reverse('notifications:list'), {'partial': '1'})
        self.assertTemplateUsed(partial, 'notifications/_notifications_panel.html')

    def test_mark_read_and_mark_all_read(self):
        first = self.mine.order_by('id').first()
        response = self.client.post(reverse('notifications:mark_read', args=[first.id]), data={'next': '/somewhere/'})
        self.assertRedirects(response, '/somewhere/', fetch_redirect_response=False)
        first.refresh_from_db()
        self.assertTrue(first.is_read)

        self.client.post(reverse('notifications:mark_all_read'))
        self.assertFalse(self.mine.filter(is_read=False).exists())

    def test_next_redirect_only_goes_to_this_site(self):
        notification = self.mine.first()
        cases = [
            ('https://evil.example.com/phish', reverse('notifications:list')),
            ('//evil.example.com/phish', reverse('notifications:list')),
            ('/somewhere/', '/somewhere/'),
        ]
        for next_url, expected in cases:
            for url in (reverse('notifications:mark_read', args=[notification.id]), reverse('notifications:mark_all_read')):
                with self.subTest(next=next_url, url=url):
                    response = self.client.post(url, data={'next': next_url})
                    self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_other_user_cannot_mark_or_see_my_notifications(self):
        notification = self.mine.first()
        self.client.login(username='other-user', password='pass1234')
        self.assertEqual(self.client.post(reverse('notifications:mark_read', args=[notification.id])).status_code, 404)
        self.client.post(reverse('notifications:mark_all_read'))
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)
        self.assertEqual(list(self.client.get(reverse('notifications:list')).context['notifications']), [])
