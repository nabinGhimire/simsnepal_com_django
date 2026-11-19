from django.db import migrations, models
import django.db.models.deletion
import nepali_datetime_field.models


def create_tables(apps, schema_editor):
    connection = schema_editor.connection
    HealthRecord = apps.get_model("sms", "StudentHealthRecord")
    Profile = apps.get_model("sms", "StudentProfile")

    if connection.vendor == "mysql":
        from django.db.utils import DatabaseError

        # The FK columns were created as varchar(9) by the model definition
        # (to_field='reg_no', db_column='student_id'), so just verify/fix collation
        student_fields = [
            (HealthRecord, HealthRecord._meta.get_field("student")),
            (Profile, Profile._meta.get_field("student")),
        ]
        for model, field in student_fields:
            try:
                schema_editor.execute(
                    "ALTER TABLE %s MODIFY %s varchar(9) "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL"
                    % (
                        schema_editor.quote_name(model._meta.db_table),
                        schema_editor.quote_name(field.column),
                    )
                )
            except Exception:
                pass


def drop_tables(apps, schema_editor):
    HealthRecord = apps.get_model("sms", "StudentHealthRecord")
    Profile = apps.get_model("sms", "StudentProfile")
    schema_editor.delete_model(Profile)
    schema_editor.delete_model(HealthRecord)


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('sms', '0025_parentmessagelog_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentHealthRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', nepali_datetime_field.models.NepaliDateField()),
                ('weight_kg', models.DecimalField(decimal_places=2, max_digits=5)),
                ('height_cm', models.DecimalField(decimal_places=2, max_digits=5)),
                ('response', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('session', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sms.edusession')),
                ('student', models.ForeignKey(db_column='student_id', on_delete=django.db.models.deletion.CASCADE, related_name='health_records', to='sms.student', to_field='reg_no')),
            ],
            options={
                'ordering': ['-date'],
            },
        ),
        migrations.CreateModel(
            name='StudentProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mother_tongue', models.CharField(blank=True, max_length=100, null=True)),
                ('other_languages', models.JSONField(blank=True, default=list)),
                ('experience_type', models.CharField(blank=True, choices=[('', 'None'), ('ece', 'Early Childhood Development & Education'), ('other_institution', 'Other Institution')], default='', max_length=30)),
                ('experience_details', models.TextField(blank=True, null=True)),
                ('special_disease', models.TextField(blank=True, null=True)),
                ('disability_details', models.TextField(blank=True, null=True)),
                ('other_details', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student', models.OneToOneField(db_column='student_id', on_delete=django.db.models.deletion.CASCADE, related_name='profile', to='sms.student', to_field='reg_no')),
            ],
        ),
        migrations.RunPython(create_tables, drop_tables),
    ]