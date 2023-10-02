import os
from urllib.parse import urlparse

from django.conf import settings
from django.http import FileResponse, HttpResponseForbidden
from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature, BadTimeSignature

from .models import AccountTier, Image, ThumbnailSize
from .serializers import AccountTierSerializer, ImageSerializer, ThumbnailSizeSerializer


def serve_image(request, signed_url):
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    try:
        data = s.loads(signed_url)
        expiring_url = data['url']
        expiry_time = data['expiry_time']
        s.loads(signed_url, max_age=expiry_time)
        url_path = urlparse(expiring_url).path
        file_path = settings.MEDIA_ROOT + url_path.replace(
            settings.MEDIA_URL, '/'
        )
        return FileResponse(open(file_path, 'rb'))
    except SignatureExpired:
        return HttpResponseForbidden('The image link has expired')
    except (BadSignature, BadTimeSignature):
        return HttpResponseForbidden('Invalid image link')


class AccountTierListView(generics.ListCreateAPIView):
    queryset = AccountTier.objects.all()
    serializer_class = AccountTierSerializer
    permission_classes = [permissions.IsAdminUser]


class AccountTierDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = AccountTier.objects.all()
    serializer_class = AccountTierSerializer
    permission_classes = [permissions.IsAdminUser]


class ThumbnailSizeListView(generics.ListCreateAPIView):
    queryset = ThumbnailSize.objects.all()
    serializer_class = ThumbnailSizeSerializer
    permission_classes = [permissions.IsAdminUser]


class ThumbnailSizeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ThumbnailSize.objects.all()
    serializer_class = ThumbnailSizeSerializer
    permission_classes = [permissions.IsAdminUser]


class ImageUploadView(generics.CreateAPIView):
    """
    Upload JPG or PNG image.
    """
    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """
        Save the uploaded image to the user's profile.
        """
        uploaded_file = self.request.FILES.get('image')
        if uploaded_file:
            if os.path.splitext(uploaded_file.name)[1].lower() in ['.jpeg', '.jpg', '.png']:
                expiry_time = self.request.data.get('expiry_time', 300)
                try:
                    expiry_time = int(expiry_time)
                    if expiry_time in range(300, 30001):
                        serializer.save(user=self.request.user, image=uploaded_file, expiry_time=expiry_time)
                    else:
                        raise serializers.ValidationError(
                            'Image expiry link duration must be between 300 and 30000.'
                        )
                except ValueError:
                    raise serializers.ValidationError('Image expiry link duration must be numbers.')
            else:
                raise serializers.ValidationError('Unsupported file extension. Only JPG and PNG are supported.')
        else:
            raise serializers.ValidationError('Image file not provided.')


class UserImagesListView(generics.ListAPIView):
    """
    List all images uploaded by the authenticated user.
    """
    serializer_class = ImageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return a queryset that includes only the images uploaded by the authenticated user.
        """
        return Image.objects.filter(user=self.request.user)


class GenerateExpiringLinkView(generics.GenericAPIView):
    """
    Generate an expiring link for an image.
    Available only for Enterprise and admin users.
    """
    queryset = Image.objects.all()
    serializer_class = ImageSerializer

    def get(self, request, *args, **kwargs):
        return self.generate_link(request, *args, **kwargs)

    def generate_link(self, request, *args, **kwargs):
        user = request.user

        if not user.is_staff and not user.userprofile.account_tier.name == 'Enterprise':
            return Response({'detail': 'You do not have permission to perform this action.'},
                            status=status.HTTP_403_FORBIDDEN)

        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        return Response(data)
