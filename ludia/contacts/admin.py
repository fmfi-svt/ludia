from django.contrib import admin

from ludia.contacts.models import Contact, ContactType, Person, Source


class ContactInline(admin.TabularInline):
    model = Contact


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    search_fields = ["first_name", "last_name", "middle_name", "university_id", "login"]
    inlines = [ContactInline]


@admin.register(ContactType)
class ContactTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    pass
