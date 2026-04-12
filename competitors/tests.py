import sys
import unittest

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competitors.models import Competitor


class CompetitorViewTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="owner", password="strong-pass-123")
        self.other_user = User.objects.create_user(username="other", password="strong-pass-123")
        self.competitor = Competitor.objects.create(
            user=self.owner,
            name="Rival",
            url="https://example.com",
            description="Direct competitor",
        )

    @unittest.skipIf(sys.version_info >= (3, 14), "Django 4.2 test client rendering is not fully compatible with Python 3.14.")
    def test_dashboard_requires_login(self) -> None:
        response = self.client.get(reverse("competitors:dashboard"))
        self.assertEqual(response.status_code, 302)

    @unittest.skipIf(sys.version_info >= (3, 14), "Django 4.2 test client rendering is not fully compatible with Python 3.14.")
    def test_user_cannot_access_other_users_competitor_detail(self) -> None:
        self.client.login(username="other", password="strong-pass-123")
        response = self.client.get(reverse("competitors:detail", args=[self.competitor.pk]))
        self.assertEqual(response.status_code, 404)

    @unittest.skipIf(sys.version_info >= (3, 14), "Django 4.2 test client rendering is not fully compatible with Python 3.14.")
    def test_authenticated_user_can_add_competitor(self) -> None:
        self.client.login(username="owner", password="strong-pass-123")
        response = self.client.post(
            reverse("competitors:dashboard"),
            {
                "name": "Another Rival",
                "url": "https://another-example.com",
                "description": "Another competitor",
                "is_active": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Competitor.objects.filter(user=self.owner, url="https://another-example.com").exists())
