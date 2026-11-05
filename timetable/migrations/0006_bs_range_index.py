"""
Replace AD-based exception index with BS range index.

The resolver filters timetable_exception by BS date_from/date_to (lexicographic
BS comparison), not by AD shadow columns. The previous index
tt_exc_school_date_from_idx was on (school_id, date_from_ad) — the AD shadow —
which MySQL's optimizer incorrectly preferred over the BS index even though
queries filter on BS columns.

This migration:
  - Removes tt_exc_school_date_from_idx (AD-based, wrong for BS filtering)
  - Adds tt_exc_school_bs_range_idx on (school_id, date_from, date_to) — the
    proper BS range index for the resolver's query:
      WHERE school_id = X AND date_from <= Y AND date_to >= Y
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timetable", "0005_backfill_ad_columns"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="timetableexception",
            name="tt_exc_school_date_from_idx",
        ),
        migrations.AddIndex(
            model_name="timetableexception",
            index=models.Index(
                fields=["school", "date_from", "date_to"],
                name="tt_exc_school_bs_range_idx",
            ),
        ),
    ]
