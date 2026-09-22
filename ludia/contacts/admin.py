from django.contrib import admin

from ludia.contacts.models import (
    Contact,
    ContactType,
    Lesson,
    Person,
    Relation,
    Source,
    Workplace,
)


class ContactInline(admin.TabularInline):
    model = Contact


class RelationInline(admin.TabularInline):
    model = Relation
    autocomplete_fields = ["workplace"]


class LessonInline(admin.TabularInline):
    model = Lesson


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    search_fields = ["first_name", "last_name", "middle_name", "university_id", "login"]
    inlines = [ContactInline, RelationInline, LessonInline]


@admin.register(ContactType)
class ContactTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    pass


@admin.register(Workplace)
class WorkplaceAdmin(admin.ModelAdmin):
    autocomplete_fields = ["parent"]
    search_fields = ["name_sk", "name_en"]
