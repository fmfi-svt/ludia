from django.core.management.base import BaseCommand

from ludia.contacts.models import ContactType

CONTACT_TYPES = (
    {
        "identifier": "phone",
        "name_sk": "Telefón",
        "name_en": "Phone",
        "icon": "lucide:phone",
        "order": 0,
    },
    {
        "identifier": "email",
        "name_sk": "Email",
        "name_en": "Email",
        "icon": "lucide:mail",
        "order": 1,
    },
    {
        "identifier": "room",
        "name_sk": "Miesnosť",
        "name_en": "Room",
        "icon": "lucide:map-pin",
        "order": 2,
    },
    {
        "identifier": "website",
        "name_sk": "Odkaz",
        "name_en": "Link",
        "icon": "lucide:globe",
        "order": 4,
    },
)


class Command(BaseCommand):
    help = "Create the default contact types when they do not already exist."

    def handle(self, *args, **options):
        created_count = 0

        for contact_type in CONTACT_TYPES:
            _, created = ContactType.objects.get_or_create(
                identifier=contact_type["identifier"], defaults=contact_type
            )
            created_count += created

        self.stdout.write(
            self.style.SUCCESS(f"Created {created_count} contact type(s).")
        )
