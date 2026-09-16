from django.urls import path

from ludia.contacts.views import person_profile

urlpatterns = [
    path("<login>/", person_profile, name="profile"),
]
