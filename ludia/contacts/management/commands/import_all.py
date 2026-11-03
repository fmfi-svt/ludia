from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Populate contact types and run CIT, Candle, and VUPCH imports, continuing after failures."

    def handle(self, *args, **options):
        commands = (
            "populate_contact_types",
            "import_cit",
            "import_candle",
            "import_vupch",
        )
        failures = []

        for name in commands:
            self.stdout.write(f"Running {name}...")
            try:
                call_command(
                    name,
                    stdout=self.stdout,
                    stderr=self.stderr,
                    verbosity=options["verbosity"],
                )
            except Exception as exc:
                failures.append(name)
                self.stderr.write(self.style.ERROR(f"{name} failed: {exc}"))

        if failures:
            raise CommandError(f"Failed imports: {', '.join(failures)}")

        self.stdout.write(self.style.SUCCESS("All imports completed successfully."))
