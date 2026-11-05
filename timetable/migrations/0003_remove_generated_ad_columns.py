# Remove STORED GENERATED clauses / triggers from AD shadow columns.
# AD shadows are now plain writable DateFields computed in model.save()
# via nepali_datetime (BS → AD accurate conversion).
#
# MySQL: ALTER COLUMN ... MODIFY ... DATE  (removes GENERATED ALWAYS AS)
# SQLite: DROP TRIGGER for each AD shadow trigger

from django.db import migrations, models


def _mysql(se):
    return se.connection.vendor == "mysql"


def _sqlite(se):
    return se.connection.vendor == "sqlite"


def fwd(apps, se):
    if _mysql(se):
        # Remove STORED GENERATED from all AD shadow columns.
        # effective_from_ad / date_from_ad / date_to_ad are NOT NULL.
        # specific_date_ad / valid_from_ad / valid_to_ad are NULLable.
        se.execute(
            "ALTER TABLE timetable_version "
            "MODIFY COLUMN effective_from_ad DATE NOT NULL"
        )
        se.execute(
            "ALTER TABLE timetable_entry "
            "MODIFY COLUMN specific_date_ad DATE NULL"
        )
        se.execute(
            "ALTER TABLE timetable_entry "
            "MODIFY COLUMN valid_from_ad DATE NULL"
        )
        se.execute(
            "ALTER TABLE timetable_entry "
            "MODIFY COLUMN valid_to_ad DATE NULL"
        )
        se.execute(
            "ALTER TABLE timetable_exception "
            "MODIFY COLUMN date_from_ad DATE NOT NULL"
        )
        se.execute(
            "ALTER TABLE timetable_exception "
            "MODIFY COLUMN date_to_ad DATE NOT NULL"
        )
    elif _sqlite(se):
        # Drop the AFTER INSERT / AFTER UPDATE triggers created in 0001.
        _triggers = [
            ("timetable_version", "effective_from_ad"),
            ("timetable_entry", "specific_date_ad"),
            ("timetable_entry", "valid_from_ad"),
            ("timetable_entry", "valid_to_ad"),
            ("timetable_exception", "date_from_ad"),
            ("timetable_exception", "date_to_ad"),
        ]
        for table, col in _triggers:
            se.execute(f"DROP TRIGGER IF EXISTS trg_{table}_{col}_ins")
            se.execute(f"DROP TRIGGER IF EXISTS trg_{table}_{col}_upd")


def rev(apps, se):
    # Reversing would re-add GENERATED clauses — not supported cleanly;
    # the AD columns are now plain computed fields in Python.
    pass


class Migration(migrations.Migration):

    # DDL (ALTER COLUMN to remove GENERATED) cannot run inside a transaction
    # on MySQL.
    atomic = False

    dependencies = [
        ("timetable", "0002_fix_id_autofield"),
    ]

    operations = [
        migrations.RunPython(fwd, rev),
        # State-only: AD fields lose editable=False (now plain writable).
        migrations.AlterField(
            model_name="timetableversion",
            name="effective_from_ad",
            field=models.DateField(
                help_text="AD shadow of effective_from, computed in save().",
            ),
        ),
        migrations.AlterField(
            model_name="timetableentry",
            name="specific_date_ad",
            field=models.DateField(
                null=True, blank=True,
                help_text="AD shadow of specific_date, computed in save().",
            ),
        ),
        migrations.AlterField(
            model_name="timetableentry",
            name="valid_from_ad",
            field=models.DateField(
                null=True, blank=True,
                help_text="AD shadow of valid_from, computed in save().",
            ),
        ),
        migrations.AlterField(
            model_name="timetableentry",
            name="valid_to_ad",
            field=models.DateField(
                null=True, blank=True,
                help_text="AD shadow of valid_to, computed in save().",
            ),
        ),
        migrations.AlterField(
            model_name="timetableexception",
            name="date_from_ad",
            field=models.DateField(
                help_text="AD shadow of date_from, computed in save().",
            ),
        ),
        migrations.AlterField(
            model_name="timetableexception",
            name="date_to_ad",
            field=models.DateField(
                help_text="AD shadow of date_to, computed in save().",
            ),
        ),
    ]
