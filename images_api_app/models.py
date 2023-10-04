import os
import logging
from io import BytesIO

from django.db import models
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from PIL import Image as PILImage

from .utils import generate_signed_url, is_valid_file_extension


logging.basicConfig(filename='image_api_app.log', level=logging.ERROR)


class ThumbnailSize(models.Model):
    height = models.PositiveIntegerField(unique=True)

    def __str__(self):
        return f"{self.height}px"


class AccountTier(models.Model):
    name = models.CharField(max_length=100)
    thumbnail_sizes = models.ManyToManyField(ThumbnailSize, blank=True)
    allow_original_link = models.BooleanField(default=False)
    allow_expiring_link = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    account_tier = models.ForeignKey(AccountTier, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.user.username


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


def validate_file_extension(value):
    ext = os.path.splitext(value.name)[1]
    if not ext:
        raise ValidationError('File extension not found.')
    if not is_valid_file_extension(value.name):
        raise ValidationError('Unsupported file extension.')


class Image(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='images/', validators=[validate_file_extension])
    thumbnails = models.ManyToManyField(ThumbnailSize, through='ImageThumbnail')
    expiring_image_link = models.CharField(max_length=2000, null=True, blank=True)
    expiry_time = models.IntegerField(
        default=300, validators=[MinValueValidator(300), MaxValueValidator(30000)])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if kwargs.get('update_fields') is None or 'expiring_image_link' not in kwargs['update_fields']:
            self.full_clean()
        super().save(*args, **kwargs)

    def get_thumbnail(self, thumbnail_size):
        thumbnail_size_instance, _ = ThumbnailSize.objects.get_or_create(height=thumbnail_size)
        thumbnail, created = ImageThumbnail.objects.get_or_create(
            image=self, thumbnail_size=thumbnail_size_instance)

        if created or not thumbnail.thumbnail:
            try:
                with PILImage.open(self.image.file) as image:
                    size = thumbnail_size
                    image.thumbnail((size, size))
                    thumb_io = BytesIO()
                    image.save(thumb_io, format=image.format)
                    thumb_filename = f'{os.path.splitext(self.image.name)[0]}_{size}.png'
                    thumbnail.thumbnail.save(
                        thumb_filename, File(thumb_io), save=True)
            except Exception as e:
                logging.error(f"An error occurred while opening the image: {e}")
                return None

        return thumbnail.thumbnail.url if thumbnail and thumbnail.thumbnail else None

    def create_expiring_link(self):
        signed_url = generate_signed_url(self.image.url, self.expiry_time)
        self.expiring_image_link = signed_url
        self.save(update_fields=['expiring_image_link'])


@receiver(post_save, sender=Image)
def update_expiring_link(sender, instance, **kwargs):
    post_save.disconnect(update_expiring_link, sender=sender)
    instance.create_expiring_link()
    post_save.connect(update_expiring_link, sender=sender)


def get_thumbnail_upload_path(instance, filename):
    size = instance.thumbnail_size.height
    return f'thumbnails/{size}/{filename}'


class ImageThumbnail(models.Model):
    image = models.ForeignKey(Image, on_delete=models.CASCADE, related_name='image_thumbnails')
    thumbnail_size = models.ForeignKey(ThumbnailSize, on_delete=models.CASCADE)
    thumbnail = models.ImageField(upload_to=get_thumbnail_upload_path, null=True, blank=True)
