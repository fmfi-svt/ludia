from debug_toolbar.toolbar import debug_toolbar_urls
from django.conf import settings
from django.conf.urls import include
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

urlpatterns = (
    [
        path("admin/", admin.site.urls),
        path("", include("ludia.users.urls")),
    ]
    + i18n_patterns(
        path("", include("ludia.contacts.urls")),
    )
    + debug_toolbar_urls()
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
