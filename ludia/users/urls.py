from django.urls.conf import include, path

urlpatterns = [
    path("oidc/", include("mozilla_django_oidc.urls")),
]
