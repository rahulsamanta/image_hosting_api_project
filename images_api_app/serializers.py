from rest_framework import serializers, fields

from .models import AccountTier, Image, ThumbnailSize, UserProfile
from .utils import get_expiring_image_link


class AccountTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountTier
        fields = '__all__'


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'


class ThumbnailSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThumbnailSize
        fields = '__all__'


class ThumbnailField(fields.Field):
    """
    Custom Field to handle the thumbnail representation based on the height.
    """
    def to_representation(self, value):
        size = int(self.field_name.split('_')[-1])
        request = self.context.get('request')
        image_url = value.get_thumbnail(size)
        return request.build_absolute_uri(image_url) if request and image_url else image_url


class ImageSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    image = serializers.SerializerMethodField()
    expiring_image_link = serializers.SerializerMethodField()
    expiry_time = serializers.IntegerField(default=300)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request') if self.context else None
        user = request.user if request else None
        if user:
            self.handle_user(user)

    class Meta:
        model = Image
        fields = '__all__'

    def handle_user(self, user):
        allowed_sizes = []
        if user.is_staff:
            allowed_sizes = ThumbnailSize.objects.values_list('height', flat=True)
        elif hasattr(user, 'userprofile') and user.userprofile.account_tier:
            if user.userprofile.account_tier.name == 'Basic':
                allowed_sizes = [200]
            elif user.userprofile.account_tier.name in ['Premium', 'Enterprise']:
                allowed_sizes = [200, 400]
        else:
            raise serializers.ValidationError("Account tier not assigned to user.")

        if not ThumbnailSize.objects.filter(height__in=allowed_sizes).exists():
            raise serializers.ValidationError(
                "Required thumbnail sizes 200 and/or 400 do not exist."
            )

        for size in allowed_sizes:
            self.fields[f'thumbnail_{size}'] = ThumbnailField(read_only=True, source='*')

    def get_thumbnail_url(self, obj, size):
        request = self.context.get('request')
        thumbnail_url = obj.get_thumbnail(size)
        return request.build_absolute_uri(thumbnail_url) if request and thumbnail_url else thumbnail_url

    def get_image(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        if user and hasattr(user, 'userprofile') and user.userprofile.account_tier:
            account_tier_name = user.userprofile.account_tier.name
            if account_tier_name in ['Premium', 'Enterprise']:
                image_url = obj.image.url
                return request.build_absolute_uri(image_url) if request else image_url
        return None

    def get_expiring_image_link(self, obj):
        request = self.context.get('request')
        return get_expiring_image_link(request, obj)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        user = request.user if request else None
        account_tier = 'Basic'
        if user and hasattr(user, 'userprofile') and user.userprofile.account_tier:
            account_tier = user.userprofile.account_tier.name

        if account_tier in ['Basic', 'Premium', 'Enterprise']:
            rep['thumbnail_200'] = self.get_thumbnail_url(instance, 200)

        if account_tier in ['Premium', 'Enterprise']:
            rep['thumbnail_400'] = self.get_thumbnail_url(instance, 400)

        thumbnails = instance.image_thumbnails.all()
        rep['thumbnails'] = [thumbnail.thumbnail_size.height for thumbnail in thumbnails]
        return rep
