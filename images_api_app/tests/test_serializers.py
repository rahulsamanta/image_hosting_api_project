from django.test import TestCase, RequestFactory
from rest_framework.exceptions import ValidationError

from .test_models import create_test_user, create_test_image
from images_api_app.models import AccountTier, Image, ThumbnailSize, UserProfile
from images_api_app.serializers import (
    ImageSerializer, AccountTierSerializer, UserProfileSerializer, ThumbnailSizeSerializer
)


class BaseSerializerTest(TestCase):

    def setUp(self):
        self.user = create_test_user()
        self.image_file = create_test_image()
        self.enterprise_tier = AccountTier.objects.create(name='Enterprise')
        self.user.userprofile.account_tier = self.enterprise_tier
        self.user.userprofile.save()
        self.thumbnail_size_200 = ThumbnailSize.objects.create(height=200)
        self.thumbnail_size_400 = ThumbnailSize.objects.create(height=400)
        self.uploaded_image = Image.objects.create(user=self.user, image=self.image_file)
        self.factory = RequestFactory()


class AccountTierSerializerTest(BaseSerializerTest):

    def test_account_tier_serializer(self):
        serializer = AccountTierSerializer(data={'name': 'Premium'})
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.assertEqual(AccountTier.objects.last().name, 'Premium')

    def test_account_tier_serializer_invalid(self):
        serializer = AccountTierSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)


class UserProfileSerializerTest(BaseSerializerTest):

    def test_user_profile_serializer(self):
        user_profile = UserProfile.objects.get(user=self.user.id)
        serializer = UserProfileSerializer(
            instance=user_profile, data={
                'user': self.user.id,
                'account_tier': self.enterprise_tier.id
            })
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data.get('user').username, 'testuser')
        self.assertEqual(serializer.validated_data.get('account_tier').name, 'Enterprise')

    def test_user_profile_serializer_non_account_tier(self):
        user_profile = UserProfile.objects.get(user=self.user.id)
        serializer = UserProfileSerializer(
            instance=user_profile, data={'user': self.user.id})
        self.assertTrue(serializer.is_valid())
        self.assertNotIn('account_tier', serializer.validated_data)


class ThumbnailSizeSerializerTest(BaseSerializerTest):

    def test_thumbnail_size_serializer(self):
        serializer = ThumbnailSizeSerializer(data={'height': 500})
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.assertEqual(ThumbnailSize.objects.last().height, 500)

    def test_thumbnail_size_serializer_duplicate_height(self):
        serializer = ThumbnailSizeSerializer(data={'height': 200})
        self.assertFalse(serializer.is_valid())
        self.assertIn('height', serializer.errors)


class ImageSerializerTest(BaseSerializerTest):

    def test_image_serializer_valid(self):
        request = self.factory.get('/')
        request.user = self.user
        serializer = ImageSerializer(data={
            'user': self.user.id, 'image': self.image_file}, context={'request': request})
        self.assertTrue(serializer.is_valid())

    def test_image_serializer_thumbnail_field(self):
        request = self.factory.get('/')
        request.user = self.user
        serializer = ImageSerializer(instance=self.uploaded_image, context={'request': request})
        data = serializer.data
        self.assertIn('thumbnail_200', data)
        self.assertIn('thumbnail_400', data)

    def test_image_serializer_handle_user_validation(self):
        self.user.userprofile.account_tier = None
        self.user.userprofile.save()
        request = self.factory.get('/')
        request.user = self.user

        with self.assertRaises(ValidationError):
            serializer = ImageSerializer(data={
                'user': self.user.id, 'image': self.image_file}, context={'request': request})
            serializer.is_valid(raise_exception=True)
