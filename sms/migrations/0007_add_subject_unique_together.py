# -*- coding: utf-8 -*-
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sms", "0006_cleanup_duplicate_subjects"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="subject",
            unique_together=(
                ("session", "branch", "grade", "section", "subject"),
                ("session", "grade", "subject_master"),
            ),
        )
    ]
