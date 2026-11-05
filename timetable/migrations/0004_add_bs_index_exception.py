# Add BS-string index on timetable_exception(school_id, date_from)
# so the resolver's BS range filter (date_from <= X AND date_to >= X)
# can use an index instead of scanning all rows.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("timetable", "0003_remove_generated_ad_columns"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="timetableexception",
            index=models.Index(
                fields=["school", "date_from"],
                name="tt_exc_school_bs_from_idx",
            ),
        ),
    ]
