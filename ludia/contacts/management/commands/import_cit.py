from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management.base import BaseCommand

from ludia.contacts.imports.cit import (
    download_exports,
    import_contacts,
    import_people,
    import_relations,
    import_workplaces,
)


class Command(BaseCommand):
    help = "Download and import people, workplaces, relations, and contacts from CIT."

    def handle(self, *args, **options):
        with TemporaryDirectory() as temporary_directory:
            store_path = Path(temporary_directory)
            download_exports(store_path)
            import_people(store_path)
            import_workplaces(store_path)
            import_relations(store_path)
            import_contacts(store_path)

        self.stdout.write(self.style.SUCCESS("Imported CIT data."))
