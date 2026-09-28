import re
from typing import TYPE_CHECKING, Any

from django.db import connection, models
from django.db.models import Q
from django.utils.dates import WEEKDAYS_ABBR
from django.utils.html import escape, format_html
from django.utils.safestring import SafeString
from django.utils.translation import get_language

from ludia.contacts.rendering import render_contact

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


def get_translation(obj: Any, key: str, language: str | None = None) -> Any:
    if language is None:
        language = get_language()

    preference = ["sk", "en"]
    if language == "en":
        preference = ["en", "sk"]

    for lang in preference:
        if hasattr(obj, "get"):
            value = obj.get(f"{key}_{lang}")
        else:
            value = getattr(obj, f"{key}_{lang}", None)

        if value:
            return value


class LanguageChoices(models.TextChoices):
    SK = "SK", "slovensky"
    EN = "EN", "english"


class Person(models.Model):
    id: int
    university_id = models.BigIntegerField(verbose_name="UOČ", unique=True)
    login = models.CharField(max_length=128, unique=True)
    orcid = models.CharField(max_length=128, blank=True)
    vupch_url = models.CharField(max_length=256, blank=True)
    title_before = models.CharField(max_length=128, blank=True)
    title_after = models.CharField(max_length=128, blank=True)
    first_name = models.CharField(max_length=128, blank=True)
    middle_name = models.CharField(max_length=128, blank=True)
    last_name = models.CharField(max_length=128, blank=True)

    lesson_set: "RelatedManager[Lesson]"
    contact_set: "RelatedManager[Contact]"
    publication_set: "RelatedManager[Publication]"

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

    def get_contacts(self, language: str | None = None) -> list["Contact"]:
        if language is None:
            language = get_language()

        contacts = self.contact_set.filter(
            Q(language="") | Q(language=language)
        ).select_related("contact_type")
        seen_contact_values = set()
        return [
            contact
            for contact in contacts
            if not (
                contact.value in seen_contact_values
                or seen_contact_values.add(contact.value)
            )
        ]


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
        return get_translation(self, "name")


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

    class Meta:
        ordering = ["contact_type", "source", "value"]

    def __str__(self) -> str:
        return self.value

    def render(self):
        return render_contact(self)


class Workplace(models.Model):
    id: int
    parent: "models.ForeignKey[Workplace | None]" = models.ForeignKey(
        "Workplace",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    parent_id: int
    cit_id = models.BigIntegerField(unique=True)
    name_sk = models.CharField(max_length=128, blank=True)
    name_en = models.CharField(max_length=128, blank=True)
    is_overriden = models.BooleanField(
        default=False, help_text="Do not update names during imports."
    )
    address = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        return get_translation(self, "name")


class Relation(models.Model):
    id: int
    cit_id = models.BigIntegerField(unique=True)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    person_id: int
    workplace = models.ForeignKey(Workplace, on_delete=models.CASCADE)
    workplace_id: int
    job_title_sk = models.CharField(max_length=256, blank=True)
    job_title_en = models.CharField(max_length=256, blank=True)

    def __str__(self) -> str:
        return f"{self.job_title} @ {self.workplace}"

    @property
    def job_title(self) -> str:
        return get_translation(self, "job_title")

    def all_workplaces(self) -> dict[str, str]:
        table = connection.ops.quote_name(Workplace._meta.db_table)
        name_sk = []
        name_en = []
        address = ""

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                WITH RECURSIVE workplaces AS (
                    SELECT parent_id, name_sk, name_en, address, 0 AS depth
                    FROM {table}
                    WHERE id = %s

                    UNION ALL

                    SELECT workplace.parent_id,
                           workplace.name_sk,
                           workplace.name_en,
                           workplace.address,
                           workplaces.depth + 1
                    FROM {table} AS workplace
                    JOIN workplaces ON workplace.id = workplaces.parent_id
                )
                SELECT name_sk, name_en, address
                FROM workplaces
                ORDER BY depth
                """,
                [self.workplace_id],
            )

            for workplace_name_sk, workplace_name_en, workplace_address in cursor:
                names = {"name_en": workplace_name_en, "name_sk": workplace_name_sk}
                name_sk.append(get_translation(names, "name", "sk"))
                name_en.append(get_translation(names, "name", "en"))
                if not address and workplace_address:
                    address = workplace_address

        data = {
            "name_sk": "\n".join(name_sk),
            "name_en": "\n".join(name_en),
            "address": address,
        }
        data["name"] = get_translation(data, "name")
        return data


class Lesson(models.Model):
    class DayChoices(models.IntegerChoices):
        MON = 0, WEEKDAYS_ABBR[0]
        TUE = 1, WEEKDAYS_ABBR[1]
        WED = 2, WEEKDAYS_ABBR[2]
        THU = 3, WEEKDAYS_ABBR[3]
        FRI = 4, WEEKDAYS_ABBR[4]
        SAT = 5, WEEKDAYS_ABBR[5]
        SUN = 6, WEEKDAYS_ABBR[6]

    id: int
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    person_id: int

    candle_id = models.IntegerField()
    day_of_week = models.IntegerField(choices=DayChoices.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    teachers = models.CharField(max_length=512, blank=True)
    type = models.CharField(max_length=30, blank=True)
    room = models.CharField(max_length=30, blank=True)
    subject_name = models.CharField(max_length=100, blank=True)
    subject_code = models.CharField(max_length=20, blank=True)
    note = models.CharField(max_length=240, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day_of_week", "start_time", "subject_code"]

    def __str__(self):
        return self.subject_name


class Publication(models.Model):
    id: int
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    person_id: int
    raw_text = models.TextField()
    display_text = models.TextField(blank=True)
    doi = models.CharField(max_length=256, blank=True)

    class Meta:
        ordering = ["display_text"]

    def __str__(self) -> str:
        return self.render_text()

    def render_text(self) -> str:
        return self.display_text or self.raw_text

    def render(self) -> SafeString:
        text = self.render_text()
        if not self.doi:
            return escape(text)

        return format_html(
            '<a href="https://doi.org/{}" target="_blank" rel="noopener noreferrer">{}</a>',
            self.doi,
            text,
        )
