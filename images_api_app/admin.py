from django.contrib import admin

from .models import AccountTier, Image, ImageThumbnail, ThumbnailSize, UserProfile

admin.site.register(AccountTier)
admin.site.register(ThumbnailSize)
admin.site.register(ImageThumbnail)
admin.site.register(Image)
admin.site.register(UserProfile)
