from django.urls import path

from ludia.contacts.views import person_list, person_profile

urlpatterns = [
    path("", person_list, name="index"),
    path("<login>/", person_profile, name="profile"),
]
