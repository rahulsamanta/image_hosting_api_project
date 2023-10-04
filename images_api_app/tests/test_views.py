import os
import shutil

from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import status

from .test_models import create_test_user, create_test_image
from images_api_app.models import AccountTier, Image, ThumbnailSize
from images_api_app.utils import generate_signed_url


class BaseViewsTest(TestCase):
    """
    Base views test set up be extended by other test cases.
    """
    client = Client()

    @classmethod
    def setUpTestData(cls):
        cls.user = create_test_user()
        cls.image = create_test_image()
        cls.enterprise_tier = AccountTier.objects.create(name='Enterprise')
        cls.user.userprofile.account_tier = cls.enterprise_tier
        cls.user.userprofile.save()
        ThumbnailSize.objects.get_or_create(height=200)
        ThumbnailSize.objects.get_or_create(height=400)
        cls.uploaded_image = Image.objects.create(user=cls.user, image=cls.image)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(os.path.join(settings.BASE_DIR, 'test_media/'))
        super().tearDownClass()


class ImageUploadViewTest(BaseViewsTest):

    def test_image_upload_view_post(self):
        self.client.force_login(self.user)
        img_file = self.image.open()
        response = self.client.post(reverse('upload_image'), {'image': img_file, 'expiry_time': 500})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data.get('image'))

    def test_image_upload_invalid_file_extension(self):
        self.client.force_login(self.user)
        txt_file_path = os.path.join(settings.MEDIA_ROOT, 'test_file.txt')

        with open(txt_file_path, 'w') as f:
            f.write('A simple text file...')

        with open(txt_file_path, 'rb') as txt_file:
            response = self.client.post(reverse('upload_image'), {'image': txt_file})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue('Unsupported file extension.' in str(response.data))

    def test_image_upload_response(self):
        self.client.force_login(self.user)
        img_file = self.image.open()
        response = self.client.post(reverse('upload_image'), {'image': img_file, 'expiry_time': 500})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        expected_fields = [
            'id',
            'user',
            'image',
            'thumbnails',
            'expiring_image_link',
            'expiry_time',
            'uploaded_at'
        ]

        for field in expected_fields:
            self.assertIn(field, response.data)

        self.assertEqual(response.data.get('user'), self.user.username)
        self.assertEqual(response.data.get('expiry_time'), 500)
        self.assertIsNotNone(response.data.get('image'))
        self.assertIsNotNone(response.data.get('expiring_image_link'))
        self.assertIsInstance(response.data.get('thumbnails'), list)

    def test_image_upload_expiring_link_invalid(self):
        self.client.force_login(self.user)
        for expiry_time in [1, 299, 30001, 99999]:
            response = self.client.post(
                reverse('upload_image'),
                {'image': self.image.open(), 'expiry_time': expiry_time}
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn(
                'Image expiry link duration must be between 300 and 30000.', str(response.data))

    def test_image_upload_expiring_link_valid(self):
        self.client.force_login(self.user)
        for expiry_time in [300, 10000, 30000]:
            response = self.client.post(
                reverse('upload_image'),
                {'image': self.image.open(), 'expiry_time': expiry_time}
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertIsNotNone(response.data.get('expiring_image_link'))


class UserImagesListViewTest(BaseViewsTest):

    def test_user_images_list_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('list_images'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertTrue(len(response.data) > 0)


class GenerateExpiringLinkViewTest(BaseViewsTest):

    def test_generate_expiring_link_view_valid(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('generate_expiring_link', args=[self.uploaded_image.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data.get('expiring_image_link'))

    def test_generate_expiring_link_view_permission(self):
        for account_tier in ['Basic', 'Premium']:
            self.user.userprofile.account_tier = AccountTier.objects.create(name=account_tier)
            self.user.userprofile.save()
            self.client.force_login(self.user)
            response = self.client.get(reverse('generate_expiring_link', args=[self.uploaded_image.id]))
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            self.assertIsNone(response.data.get('expiring_image_link'))


class ServeImageViewTest(BaseViewsTest):

    def test_serve_image_view_valid(self):
        signed_url = self.uploaded_image.expiring_image_link
        response = self.client.get(reverse('serve_image', args=[signed_url]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_serve_image_view_expired(self):
        signed_url = generate_signed_url('http://test.com', 0)
        response = self.client.get(reverse('serve_image', args=[signed_url]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AuthenticationTest(BaseViewsTest):

    def test_unauthenticated_users(self):
        views = [
            reverse('account_tier_list'),
            reverse('account_tier_detail', args=[self.enterprise_tier.id]),
            reverse('upload_image'),
            reverse('list_images'),
            reverse('generate_expiring_link', args=[self.uploaded_image.id]),
            reverse('thumbnail_size_list'),
            reverse('thumbnail_size_detail', args=[ThumbnailSize.objects.first().id]),
        ]

        for view in views:
            response = self.client.get(view)
            self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_302_FOUND])

    def test_authenticated_with_permission(self):
        self.client.force_login(self.user)

        common_views = {
            reverse('list_images'): status.HTTP_200_OK,
            reverse('generate_expiring_link', args=[self.uploaded_image.id]): status.HTTP_200_OK,
        }

        admin_only_views = {
            reverse('account_tier_list'): status.HTTP_200_OK,
            reverse('account_tier_detail', args=[self.enterprise_tier.id]): status.HTTP_200_OK,
            reverse('thumbnail_size_list'): status.HTTP_200_OK,
            reverse('thumbnail_size_detail', args=[ThumbnailSize.objects.first().id]): status.HTTP_200_OK,
        }

        for view, expected_status in common_views.items():
            response = self.client.get(view)
            self.assertEqual(response.status_code, expected_status)

        for view in admin_only_views:
            response = self.client.get(view)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        admin_user = User.objects.create_superuser(username='admin', password='adminpass', email='admin@test.com')
        self.client.force_login(admin_user)

        for view, expected_status in admin_only_views.items():
            response = self.client.get(view)
            self.assertEqual(response.status_code, expected_status)
