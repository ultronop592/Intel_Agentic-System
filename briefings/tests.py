import sys
import unittest

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from briefings.models import Briefing
from competitors.models import Competitor


class BriefingViewTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="owner", password="strong-pass-123")
        self.other_user = User.objects.create_user(username="other", password="strong-pass-123")
        self.competitor = Competitor.objects.create(
            user=self.owner,
            name="Rival",
            url="https://example.com",
        )
        self.briefing = Briefing.objects.create(
            user=self.owner,
            competitor=self.competitor,
            content="## What They Do\nRival builds analytics tools.",
            status=Briefing.STATUS_COMPLETED,
        )

    @unittest.skipIf(sys.version_info >= (3, 14), "Django 4.2 test client rendering is not fully compatible with Python 3.14.")
    def test_briefing_list_requires_login(self) -> None:
        response = self.client.get(reverse("briefings:list"))
        self.assertEqual(response.status_code, 302)

    @unittest.skipIf(sys.version_info >= (3, 14), "Django 4.2 test client rendering is not fully compatible with Python 3.14.")
    def test_user_cannot_access_other_users_briefing(self) -> None:
        self.client.login(username="other", password="strong-pass-123")
        response = self.client.get(reverse("briefings:detail", args=[self.briefing.pk]))
        self.assertEqual(response.status_code, 404)

    @unittest.skipIf(sys.version_info >= (3, 14), "Django 4.2 test client rendering is not fully compatible with Python 3.14.")
    def test_owner_can_view_briefing_detail(self) -> None:
        self.client.login(username="owner", password="strong-pass-123")
        response = self.client.get(reverse("briefings:detail", args=[self.briefing.pk]))
        self.assertContains(response, "What They Do")
