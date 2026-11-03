from django.conf import settings
from django.middleware.locale import LocaleMiddleware as DjangoLocaleMiddleware
from django.utils import translation


class LocaleMiddleware(DjangoLocaleMiddleware):
    """Select language by URL, then cookie, then default; ignore Accept-Language."""

    def process_request(self, request):
        language = translation.get_language_from_path(request.path_info)
        if not language:
            language = settings.LANGUAGE_CODE
            cookie_language = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
            if cookie_language:
                try:
                    language = translation.get_supported_language_variant(
                        cookie_language
                    )
                except LookupError:
                    pass

        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()
