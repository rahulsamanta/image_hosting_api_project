from django.urls import path

from .views import (
    AccountTierListView, AccountTierDetailView, ImageUploadView, UserImagesListView,
    GenerateExpiringLinkView, ThumbnailSizeListView, ThumbnailSizeDetailView, serve_image
)

urlpatterns = [
    path('account-tier/', AccountTierListView.as_view(), name='account_tier_list'),
    path('account-tier/<int:pk>/', AccountTierDetailView.as_view(), name='account_tier_detail'),
    path('upload/', ImageUploadView.as_view(), name='upload_image'),
    path('list/', UserImagesListView.as_view(), name='list_images'),
    path('expiring-link/<int:pk>/', GenerateExpiringLinkView.as_view(), name='generate_expiring_link'),
    path('thumbnail-size/', ThumbnailSizeListView.as_view(), name='thumbnail_size_list'),
    path('thumbnail-size/<int:pk>/', ThumbnailSizeDetailView.as_view(), name='thumbnail_size_detail'),
    path('serve-image/<str:signed_url>/', serve_image, name='serve_image'),
]
