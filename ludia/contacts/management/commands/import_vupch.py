from django.core.management.base import BaseCommand

from ludia.contacts.imports.vupch import import_vupch
from ludia.contacts.imports.vupch_format import format_doi_publications


class Command(BaseCommand):
    help = "Import ORCIDs and publications from VUPCH."

    def handle(self, *args, **options):
        import_vupch()
        self.stdout.write(self.style.SUCCESS("Imported VUPCH data."))
        format_doi_publications()
        self.stdout.write(self.style.SUCCESS("Formatted DOI publications."))
