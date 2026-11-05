# Backfill AD shadow columns (_ad) from canonical BS sources using
# nepali_datetime (accurate BS→AD conversion).
#
# Prior to migration 0003, AD shadows were stored using the BS-57
# approximation (BS year - 57), which can be off by up to ~1 day.
# This migration recomputes every _ad column from its BS source via
# nepali_datetime.date(y, m, d).to_datetime_date(). Idempotent.

from __future__ import annotations

import datetime

from django.db import migrations

import nepali_datetime


def _bs_to_ad(bs_str: str) -> datetime.date:
    y, m, d = (int(p) for p in bs_str.split("-"))
    return nepali_datetime.date(y, m, d).to_datetime_date()


def fwd(apps, se):
    TimetableVersion = apps.get_model("timetable", "TimetableVersion")
    TimetableEntry = apps.get_model("timetable", "TimetableEntry")
    TimetableException = apps.get_model("timetable", "TimetableException")

    # TimetableVersion.effective_from_ad from effective_from
    for v in TimetableVersion.objects.all():
        if v.effective_from:
            v.effective_from_ad = _bs_to_ad(v.effective_from)
            v.save(update_fields=["effective_from_ad"])

    # TimetableEntry AD shadows from BS columns
    for e in TimetableEntry.objects.all():
        fields = {}
        if e.specific_date:
            fields["specific_date_ad"] = _bs_to_ad(e.specific_date)
        else:
            fields["specific_date_ad"] = None
        if e.valid_from:
            fields["valid_from_ad"] = _bs_to_ad(e.valid_from)
        else:
            fields["valid_from_ad"] = None
        if e.valid_to:
            fields["valid_to_ad"] = _bs_to_ad(e.valid_to)
        else:
            fields["valid_to_ad"] = None
        if fields:
            TimetableEntry.objects.filter(pk=e.pk).update(**fields)

    # TimetableException AD shadows from BS columns
    for ex in TimetableException.objects.all():
        fields = {}
        if ex.date_from:
            fields["date_from_ad"] = _bs_to_ad(ex.date_from)
        if ex.date_to:
            fields["date_to_ad"] = _bs_to_ad(ex.date_to)
        if fields:
            TimetableException.objects.filter(pk=ex.pk).update(**fields)


def rev(apps, se):
    # No reverse: reverting would re-introduce inaccurate BS-57 values.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("timetable", "0004_add_bs_index_exception"),
    ]

    operations = [
        migrations.RunPython(fwd, rev),
    ]
