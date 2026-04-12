import sys
import unittest

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile


class AccountsTests(TestCase):
    def test_profile_created_on_user_signup(self) -> None:
        user = User.objects.create_user(username="founder", password="strong-pass-123")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    @unittest.skipIf(sys.version_info >= (3, 14), "Django 4.2 test rendering is not fully compatible with Python 3.14.")
    def test_signup_view_creates_user_and_logs_in(self) -> None:
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "first_name": "Asha",
                "username": "asha",
                "email": "asha@example.com",
                "password1": "very-strong-pass-123",
                "password2": "very-strong-pass-123",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="asha").exists())
        self.assertTrue(response.context["user"].is_authenticated)
