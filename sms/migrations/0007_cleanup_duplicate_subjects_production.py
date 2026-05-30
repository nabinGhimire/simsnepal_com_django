from django.db import migrations, models

def cleanup_duplicate_subjects(apps, schema_editor):
    Subject = apps.get_model('sms', 'Subject')
    # Find duplicate groups (session, grade, subject_master) with more than one record
    from django.db.models import Count, Q
    dup_groups = (
        Subject.objects.values('session', 'grade', 'subject_master')
        .annotate(cnt=Count('id'))
        .filter(cnt__gt=1)
    )
    for grp in dup_groups:
        # Keep the record with status=True (or the earliest if multiple True)
        keep_qs = Subject.objects.filter(
            session_id=grp['session'],
            grade_id=grp['grade'],
            subject_master_id=grp['subject_master'],
            status=True
        ).order_by('id')
        if keep_qs.exists():
            keep_id = keep_qs.first().id
            # Delete all others (including any with status=False)
            Subject.objects.filter(
                session_id=grp['session'],
                grade_id=grp['grade'],
                subject_master_id=grp['subject_master']
            ).exclude(id=keep_id).delete()
        else:
            # No record with status=True, keep the earliest record regardless of status
            keep_id = (
                Subject.objects.filter(
                    session_id=grp['session'],
                    grade_id=grp['grade'],
                    subject_master_id=grp['subject_master']
                ).order_by('id').first().id
            )
            Subject.objects.filter(
                session_id=grp['session'],
                grade_id=grp['grade'],
                subject_master_id=grp['subject_master']
            ).exclude(id=keep_id).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('sms', '0006_alter_subject_unique_together'),
    ]

    operations = [
        migrations.RunPython(cleanup_duplicate_subjects, reverse_code=migrations.RunPython.noop),
    ]
