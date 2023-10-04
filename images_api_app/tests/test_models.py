from io import BytesIO
import os
import shutil

from django.test import TestCase
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from PIL import Image as PILImage

from images_api_app.models import (
    AccountTier, UserProfile, ThumbnailSize, Image, ImageThumbnail, get_thumbnail_upload_path
)
from images_api_app.utils import is_valid_file_extension


def create_test_user(username='testuser'):
    return User.objects.create(username=username)


def create_test_image(file_name="test_image.png", format='PNG', color='blue', size=(500, 500)):
    img = PILImage.new('RGB', size, color=color)
    img_io = BytesIO()
    img.save(img_io, format=format)
    img_io.seek(0)
    return SimpleUploadedFile(file_name, img_io.getvalue(), content_type=f"image/{format.lower()}")


class ThumbnailSizeModelTest(TestCase):

    def test_string_representation(self):
        thumbnail_size = ThumbnailSize(height=200)
        self.assertEqual(str(thumbnail_size), "200px")

    def test_unique_height_constraint(self):
        ThumbnailSize.objects.create(height=300)

        with self.assertRaises(ValidationError):
            duplicate_thumbnail = ThumbnailSize(height=300)
            duplicate_thumbnail.full_clean()
            duplicate_thumbnail.save()


class AccountTierModelTest(TestCase):

    def test_string_representation(self):
        account_tier = AccountTier(name="Basic")
        self.assertEqual(str(account_tier), "Basic")

    def test_many_to_many_relationship_with_thumbnail_size(self):
        thumbnail_size_200 = ThumbnailSize.objects.create(height=200)
        thumbnail_size_300 = ThumbnailSize.objects.create(height=300)
        thumbnail_size_400 = ThumbnailSize.objects.create(height=400)
        account_tier = AccountTier.objects.create(name="Enterprise")
        account_tier.thumbnail_sizes.add(thumbnail_size_200, thumbnail_size_300, thumbnail_size_400)
        fetched_account_tier = AccountTier.objects.get(name="Enterprise")
        self.assertEqual(fetched_account_tier.thumbnail_sizes.count(), 3)
        self.assertTrue(fetched_account_tier.thumbnail_sizes.filter(height=200).exists())
        self.assertTrue(fetched_account_tier.thumbnail_sizes.filter(height=300).exists())
        self.assertTrue(fetched_account_tier.thumbnail_sizes.filter(height=400).exists())


class UserProfileModelTest(TestCase):

    def setUp(self):
        self.user = create_test_user()
        self.account_tier_basic = AccountTier.objects.create(name="Basic")
        self.account_tier_premium = AccountTier.objects.create(name="Premium")

    def test_string_representation(self):
        self.assertEqual(str(self.user.userprofile), "testuser")

    def test_userprofile_auto_creation(self):
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())

        new_user = User.objects.create(username='anothertestuser')
        self.assertTrue(UserProfile.objects.filter(user=new_user).exists())

    def test_account_tier_assignment(self):
        self.user.userprofile.account_tier = self.account_tier_basic
        self.user.userprofile.save()
        self.assertEqual(self.user.userprofile.account_tier, self.account_tier_basic)

        self.user.userprofile.account_tier = self.account_tier_premium
        self.user.userprofile.save()
        self.assertEqual(self.user.userprofile.account_tier, self.account_tier_premium)

    def test_user_deletion_userprofile_cascade(self):
        user_profile_id = self.user.userprofile.id
        self.user.delete()

        with self.assertRaises(UserProfile.DoesNotExist):
            UserProfile.objects.get(id=user_profile_id)


class BaseImageModelTest(TestCase):
    """
    Base Image model test set up to be extended by other test cases.
    """
    def setUp(self):
        self.user = create_test_user()
        self.image = create_test_image()


class ImageModelTest(BaseImageModelTest):

    def setUp(self):
        super().setUp()
        self.unsupported_image = create_test_image(
            file_name="test_image.tiff", format='TIFF', color='red', size=(100, 100))

    def test_image_creation(self):
        image_instance = Image.objects.create(user=self.user, image=self.image)
        self.assertTrue(is_valid_file_extension(image_instance.image.name))

    def test_image_valid_extensions(self):
        valid_extensions = ['.jpeg', '.jpg', '.png']
        for ext in valid_extensions:
            test_image = create_test_image(file_name=f"test_image{ext}")
            image_instance = Image.objects.create(user=self.user, image=test_image)
            self.assertTrue(is_valid_file_extension(image_instance.image.name))

    def test_image_unsupported_extension(self):
        with self.assertRaises(ValidationError):
            Image.objects.create(user=self.user, image=self.unsupported_image)

    def test_image_invalid_extension(self):
        with self.assertRaises(ValidationError):
            Image.objects.create(user=self.user, image=SimpleUploadedFile(
              "test_image.txt", b"ABC123", content_type="text/plain"))

    def test_thumbnail_creation(self):
        image_instance = Image.objects.create(user=self.user, image=self.image)
        ThumbnailSize.objects.create(height=50)
        url = image_instance.get_thumbnail(50)
        self.assertIsNotNone(url)

    def test_thumbnail_retrieval(self):
        image_instance = Image.objects.create(user=self.user, image=self.image)
        thumbnail_size = ThumbnailSize.objects.create(height=50)
        ImageThumbnail.objects.create(
            image=image_instance, thumbnail_size=thumbnail_size, thumbnail=self.image)
        url = image_instance.get_thumbnail(50)
        self.assertIsNotNone(url)

    def test_expiring_link_signal_create(self):
        image_instance = Image.objects.create(user=self.user, image=self.image)
        self.assertIsNotNone(image_instance.expiring_image_link)

    def test_expiring_link_signal_update(self):
        image_instance = Image.objects.create(user=self.user, image=self.image)
        original_link = image_instance.expiring_image_link
        image_instance.expiry_time = 500
        image_instance.save()
        self.assertNotEqual(original_link, image_instance.expiring_image_link)

    def test_expiry_time_outside_range_low(self):
        with self.assertRaises(ValidationError):
            image_instance = Image(user=self.user, image=self.image, expiry_time=299)
            image_instance.full_clean()
            image_instance.save()

    def test_expiry_time_outside_range_high(self):
        with self.assertRaises(ValidationError):
            image_instance = Image(user=self.user, image=self.image, expiry_time=30001)
            image_instance.full_clean()
            image_instance.save()


class ImageThumbnailModelTest(BaseImageModelTest):

    def setUp(self):
        super().setUp()
        self.image_instance = Image.objects.create(user=self.user, image=self.image)
        self.thumbnail_size = ThumbnailSize.objects.create(height=100)
        self.thumbnail = ImageThumbnail.objects.create(
            image=self.image_instance, thumbnail_size=self.thumbnail_size, thumbnail=self.image)

    def tearDown(self):
        shutil.rmtree(os.path.join(settings.BASE_DIR, 'test_media/'))
        super().tearDown()

    def test_image_thumbnail_creation(self):
        thumbnail = ImageThumbnail.objects.create(
            image=self.image_instance, thumbnail_size=self.thumbnail_size, thumbnail=self.image)
        self.assertEqual(thumbnail.image, self.image_instance)
        self.assertEqual(thumbnail.thumbnail_size, self.thumbnail_size)

    def test_thumbnail_upload_path_200px(self):
        thumbnail_size_instance = ThumbnailSize.objects.create(height=200)
        thumbnail_instance = ImageThumbnail(
            image=self.image_instance, thumbnail_size=thumbnail_size_instance)
        expected_path = 'thumbnails/200/test_image.png'
        self.assertEqual(
            get_thumbnail_upload_path(thumbnail_instance, "test_image.png"), expected_path)

    def test_thumbnail_upload_path_400px(self):
        thumbnail_size_instance = ThumbnailSize.objects.create(height=400)
        thumbnail_instance = ImageThumbnail(
            image=self.image_instance, thumbnail_size=thumbnail_size_instance)
        expected_path = 'thumbnails/400/test_image.png'
        self.assertEqual(
            get_thumbnail_upload_path(thumbnail_instance, "test_image.png"), expected_path)

    def test_image_deletion_thumbnail_cascade(self):
        thumbnail_id = self.thumbnail.id
        self.image_instance.delete()

        with self.assertRaises(ImageThumbnail.DoesNotExist):
            ImageThumbnail.objects.get(id=thumbnail_id)
