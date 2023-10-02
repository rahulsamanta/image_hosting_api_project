from django.urls import reverse
from django.conf import settings
from itsdangerous import URLSafeTimedSerializer


def generate_signed_url(url, expiry_time):
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    data = {'url': url, 'expiry_time': expiry_time}
    signed_url = s.dumps(data)
    return signed_url


def get_expiring_image_link(request, obj):
    user = request.user if request else None
    if user and hasattr(user, 'userprofile') and user.userprofile.account_tier:
        if user.is_staff or user.userprofile.account_tier.name == 'Enterprise':
            if obj.image:
                signed_url = generate_signed_url(
                    request.build_absolute_uri(obj.image.url), obj.expiry_time)
                serve_image_url = reverse('serve_image', args=[signed_url])
                return request.build_absolute_uri(serve_image_url)
    return None
