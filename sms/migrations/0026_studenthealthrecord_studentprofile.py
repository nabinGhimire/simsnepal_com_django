from django.db import migrations, models
import django.db.models.deletion
import nepali_datetime_field.models


# ``sms_student.reg_no`` (the primary key this app references) is stored with the
# utf8mb4_general_ci collation while newer tables inherit the database default
# utf8mb4_unicode_ci. MySQL refuses a foreign key when the referencing and
# referenced columns use different collations, so the new ``student_id`` columns
# are created explicitly with the same collation as ``sms_student.reg_no``.
STUDENT_FK_SUFFIX = "_fk_%(to_table)s_%(to_column)s"


def create_tables(apps, schema_editor):
    connection = schema_editor.connection
    HealthRecord = apps.get_model("sms", "StudentHealthRecord")
    Profile = apps.get_model("sms", "StudentProfile")

    student_fields = [
        (HealthRecord, HealthRecord._meta.get_field("student")),
        (Profile, Profile._meta.get_field("student")),
    ]

    if connection.vendor == "mysql":
        # Create the tables without the student FK first, align the column
        # collation, then add the constraint.
        for model, field in student_fields:
            field.db_constraint = False

    schema_editor.create_model(HealthRecord)
    schema_editor.create_model(Profile)

    if connection.vendor == "mysql":
        for model, field in student_fields:
            schema_editor.execute(
                "ALTER TABLE %s MODIFY %s varchar(9) "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL"
                % (
                    schema_editor.quote_name(model._meta.db_table),
                    schema_editor.quote_name(field.column),
                )
            )
            field.db_constraint = True
            schema_editor.execute(
                schema_editor._create_fk_sql(model, field, STUDENT_FK_SUFFIX)
            )


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
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
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
                        ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='health_records', to='sms.student')),
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
                        ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to='sms.student')),
                    ],
                ),
            ],
        ),
        migrations.RunPython(create_tables, drop_tables),
    ]
