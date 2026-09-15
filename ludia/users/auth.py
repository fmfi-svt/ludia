from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import User


def logout_url(request):
    return "https://id.trojsten.sk/oauth/logout"


class OIDC(OIDCAuthenticationBackend):
    def filter_users_by_claims(self, claims):
        uid = claims.get("sub")
        if not uid:
            return User.objects.none()
        return User.objects.filter(oidc_sub=uid)

    def create_user(self, claims):
        user = User()
        self._update_user(user, claims)
        user.save()

        return user

    def update_user(self, user, claims):
        self._update_user(user, claims)
        user.save()

        return user

    def _update_user(self, user, claims):
        user.oidc_sub = claims.get("sub")
        user.email = claims.get("email")
        user.username = claims.get("preferred_username")
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
