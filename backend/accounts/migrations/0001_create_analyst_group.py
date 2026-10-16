"""Grup dasar. Izin ditambahkan saat model domain tersedia; PRD tidak merinci jabatan (FR-006)."""

from django.db import migrations

ANALYST_GROUP = "analyst"


def create_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name=ANALYST_GROUP)


def remove_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=ANALYST_GROUP).delete()


class Migration(migrations.Migration):
    dependencies = [("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(create_group, remove_group)]
