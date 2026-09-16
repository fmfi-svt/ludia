import re

from django.db import connection, models
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

    class Meta:
        ordering = ["contact_type", "source"]

    def __str__(self) -> str:
        return self.value


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
    name_sk = models.CharField(max_length=128)
    name_en = models.CharField(max_length=128)
    address = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        if get_language() == "sk":
            return self.name_sk
        return self.name_en


class Relation(models.Model):
    id: int
    cit_id = models.BigIntegerField(unique=True)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    person_id: int
    workplace = models.ForeignKey(Workplace, on_delete=models.CASCADE)
    workplace_id: int
    job_title = models.CharField(max_length=256)

    def __str__(self) -> str:
        return f"{self.job_title} @ {self.workplace}"

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
                name_sk.append(workplace_name_sk)
                name_en.append(workplace_name_en)
                if not address and workplace_address:
                    address = workplace_address

        data = {
            "name_sk": "\n".join(name_sk),
            "name_en": "\n".join(name_en),
            "address": address,
        }
        data["name"] = data[f"name_{get_language()}"]
        return data
