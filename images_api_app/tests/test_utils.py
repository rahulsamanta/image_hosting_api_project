from django.test import TestCase, RequestFactory
from django.urls import reverse
from urllib.parse import urlparse

from .test_models import create_test_user, create_test_image
from images_api_app.models import AccountTier, Image
from images_api_app.utils import generate_signed_url, get_expiring_image_link, is_valid_file_extension


class UtilsTestCase(TestCase):

    def setUp(self):
        self.user = create_test_user()
        self.test_image = create_test_image()
        self.basic_tier = AccountTier.objects.create(name='Basic')
        self.premium_tier = AccountTier.objects.create(name='Premium')
        self.enterprise_tier = AccountTier.objects.create(name='Enterprise')
        self.user.userprofile.account_tier = self.enterprise_tier
        self.user.userprofile.save()
        self.image = Image.objects.create(user=self.user, image=self.test_image)
        self.factory = RequestFactory()

    def test_generate_signed_url(self):
        signed_url = generate_signed_url('http://test.com', 300)
        self.assertIsNotNone(signed_url)

    def test_get_expiring_image_link(self):
        request = self.factory.get('/')
        request.user = self.user
        actual_path = get_expiring_image_link(request, self.image)
        domain = urlparse(request.build_absolute_uri()).netloc
        expected_url = f"http://{domain}{self.image.image.url}"
        signed_url = generate_signed_url(expected_url, 300)
        expected_path = f"http://testserver{reverse('serve_image', args=[signed_url])}"
        self.assertEqual(expected_path, actual_path)

    def test_expiring_link_no_account_tier(self):
        self.user.userprofile.account_tier = None
        request = self.factory.get('/')
        request.user = self.user
        result = get_expiring_image_link(request, self.image)
        self.assertIsNone(result)

    def test_expiring_link_non_enterprise_user(self):
        profile = self.user.userprofile
        for profile.account_tier in [self.basic_tier, self.premium_tier]:
            profile.save()
            request = self.factory.get('/')
            request.user = self.user
            result = get_expiring_image_link(request, self.image)
            self.assertIsNone(result)

    def test_valid_file_extensions(self):
        valid_extensions = ["test_image.jpg", "test_image.JPG", "test_image.jpeg", "test_image.png"]
        for ext in valid_extensions:
            self.assertTrue(is_valid_file_extension(ext))

    def test_invalid_file_extensions(self):
        invalid_extensions = ["test_image", "test_image.tiff", "test_image.txt"]
        for ext in invalid_extensions:
            self.assertFalse(is_valid_file_extension(ext))
