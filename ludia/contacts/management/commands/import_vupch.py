from django.core.management.base import BaseCommand

from ludia.contacts.imports.vupch import import_vupch


class Command(BaseCommand):
    help = "Import ORCIDs and publications from VUPCH."

    def handle(self, *args, **options):
        import_vupch()
        self.stdout.write(self.style.SUCCESS("Imported VUPCH data."))
