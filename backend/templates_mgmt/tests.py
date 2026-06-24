from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


class TemplateApiAuthTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="template-owner",
            email="template-owner@example.com",
            password="StrongPass123!",
        )

    def test_templates_endpoint_rejects_anonymous_requests(self):
        response = self.client.get(reverse("templates-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_templates_endpoint_accepts_jwt_authentication(self):
        refresh = RefreshToken.for_user(self.user)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        response = self.client.get(reverse("templates-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
