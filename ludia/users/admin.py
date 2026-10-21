from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User

admin.site.site_header = admin.site.site_title = "Ľudia FMFI"

admin.site.register(User, UserAdmin)
