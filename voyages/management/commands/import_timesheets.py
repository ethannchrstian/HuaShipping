"""Import the historical time sheets (docs/05-import-mapping.md).

    python manage.py import_timesheets            # from the committed JSON dump
    python manage.py import_timesheets --replace  # wipe voyages and re-import

Refresh the dump first if the Excel files changed:
    python tools/dump_timesheets.py
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from voyages.importer import import_all
from voyages.models import Voyage


class Command(BaseCommand):
    help = "One-time import of the historical Excel time sheets, with verification report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            default="docs/reference/timesheets-raw.json",
            help="Sheet dump produced by tools/dump_timesheets.py",
        )
        parser.add_argument(
            "--replace", action="store_true", help="Delete existing voyages first"
        )
        parser.add_argument(
            "--report", default="import-report.md", help="Where to write the report"
        )

    def handle(self, *args, **options):
        source = Path(options["json"])
        if not source.exists():
            raise CommandError(f"dump not found: {source}")
        if Voyage.objects.exists():
            if not options["replace"]:
                raise CommandError("voyages already exist — rerun with --replace to re-import")
            Voyage.objects.all().delete()  # parcels/activities/costs cascade

        sheets = json.loads(source.read_text(encoding="utf-8"))
        with transaction.atomic():
            report = import_all(sheets)

        Path(options["report"]).write_text(report.as_markdown(), encoding="utf-8")
        for r in report.results:
            marker = self.style.SUCCESS("OK      ") if not r.mismatches else self.style.WARNING("MISMATCH")
            flags = f"  ({len(r.flags)} flag)" if r.flags else ""
            self.stdout.write(f"{marker} {r.sheet_name}: {r.created_activities} aktivitas{flags}")
        mismatching = sum(1 for r in report.results if r.mismatches)
        self.stdout.write(
            f"\n{len(report.results)} voyage diimpor; {mismatching} dengan selisih vs sheet "
            f"(lihat {options['report']})"
        )
