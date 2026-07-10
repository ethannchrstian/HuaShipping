"""Seed the ActivityType lookup from the domain registry.

domain.model.ACTIVITY_TYPES is the source of truth (its semantics are frozen by
the calculation tests); this migration copies it into the DB so activities get
referential integrity. tests/voyages/test_domain_bridge.py asserts the table
and the registry never drift apart.
"""

from django.db import migrations


def seed(apps, schema_editor):
    from domain.model import ACTIVITY_TYPES

    ActivityType = apps.get_model("voyages", "ActivityType")
    for i, t in enumerate(ACTIVITY_TYPES.values()):
        ActivityType.objects.create(
            code=t.code,
            label_id=t.label_id,
            phase=t.phase.value,
            is_sailing=t.is_sailing,
            sort_hint=i,
        )


def unseed(apps, schema_editor):
    apps.get_model("voyages", "ActivityType").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("voyages", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
