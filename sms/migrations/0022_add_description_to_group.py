from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('sms', '0021_alter_studentparentgroup_student'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='description',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
