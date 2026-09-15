import re

from django.db import models
from django.utils.translation import get_language


class LanguageChoices(models.TextChoices):
    SK = "SK", "slovensky"
    EN = "EN", "english"


class Person(models.Model):
    id: int
    university_id = models.BigIntegerField(verbose_name="UOČ", unique=True)
    login = models.CharField(max_length=128, unique=True)
    title_before = models.CharField(max_length=128, blank=True)
    title_after = models.CharField(max_length=128, blank=True)
    first_name = models.CharField(max_length=128, blank=True)
    middle_name = models.CharField(max_length=128, blank=True)
    last_name = models.CharField(max_length=128, blank=True)

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        name = f"{self.first_name} {self.middle_name} {self.last_name}"
        if self.title_before:
            name = f"{self.title_before} {name}"
        if self.title_after:
            name = f"{name}, {self.title_after}"
        return re.sub(r"\s+", " ", name)


class ContactType(models.Model):
    id: int
    name_sk = models.CharField(max_length=128)
    name_en = models.CharField(max_length=128)
    icon = models.CharField(max_length=128, blank=True)
    identifier = models.CharField(max_length=128, unique=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        if get_language() == "sk":
            return self.name_sk
        return self.name_en


class Source(models.Model):
    id: int
    identifier = models.CharField(max_length=128, unique=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self) -> str:
        return self.identifier


class Contact(models.Model):
    id: int
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    person_id: int
    contact_type = models.ForeignKey(ContactType, on_delete=models.CASCADE)
    contact_type_id: int
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    source_id: int

    value = models.TextField(blank=True)
    language = models.CharField(blank=True, choices=LanguageChoices.choices)
    source_identifier = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.value
