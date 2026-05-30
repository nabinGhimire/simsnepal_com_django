# -*- coding: utf-8 -*-
from django.db import migrations, models


def cleanup_duplicate_subjects(apps, schema_editor):
    Subject = apps.get_model("sms", "Subject")
    from django.db.models import Count

    # Find groups with duplicates
    dup_groups = (
        Subject.objects.values("session", "grade", "subject_master")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
    )
    for grp in dup_groups:
        # Prefer a record with status=True; otherwise keep the earliest
        keep = (
            Subject.objects.filter(
                session_id=grp["session"],
                grade_id=grp["grade"],
                subject_master_id=grp["subject_master"],
                status=True,
            )
            .order_by("id")
            .first()
        )
        if not keep:
            keep = (
                Subject.objects.filter(
                    session_id=grp["session"],
                    grade_id=grp["grade"],
                    subject_master_id=grp["subject_master"],
                )
                .order_by("id")
                .first()
            )
        # Delete everything else
        Subject.objects.filter(
            session_id=grp["session"],
            grade_id=grp["grade"],
            subject_master_id=grp["subject_master"],
        ).exclude(id=keep.id).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("sms", "0005_alter_subjectmaster_canonical_name_and_more"),
    ]

    operations = [migrations.RunPython(cleanup_duplicate_subjects, migrations.RunPython.noop)]
