from pathlib import Path

from django.core.management.base import BaseCommand

from ludia.contacts.imports.fmfi import import_contacts


class Command(BaseCommand):
    help = "Import contacts from an FMFI CSV file."

    def add_arguments(self, parser):
        parser.add_argument("path", type=Path, help="Path to the FMFI CSV file")

    def handle(self, *args, **options):
        with options["path"].open(encoding="utf-8-sig", newline="") as reader:
            import_contacts(reader)
        self.stdout.write(self.style.SUCCESS("Imported FMFI contacts."))
