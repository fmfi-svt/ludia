from django.core.management.base import BaseCommand

from ludia.contacts.imports.candle import import_timetables


class Command(BaseCommand):
    help = "Import timetables from Candle."

    def handle(self, *args, **options):
        import_timetables()
        self.stdout.write(self.style.SUCCESS("Imported Candle timetables."))
