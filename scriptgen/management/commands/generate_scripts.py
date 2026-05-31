"""Management command: python manage.py generate_scripts --count 5"""

from django.core.management.base import BaseCommand

from scriptgen.services.pipeline import run


class Command(BaseCommand):
    help = "Generate Nick Jackson scripts for today"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=5,
            help="Number of scripts to generate (default: 5)",
        )

    def handle(self, *args, **options):
        count = options["count"]
        self.stdout.write(f"Starting script generation (count={count})...")

        gen_run = run(count=count)

        self.stdout.write(
            self.style.SUCCESS(
                f"Run complete: {gen_run.num_passed}/{count} passed | "
                f"Status: {gen_run.status}"
            )
        )
        if gen_run.log:
            self.stdout.write("\n--- Run Log ---")
            self.stdout.write(gen_run.log)
