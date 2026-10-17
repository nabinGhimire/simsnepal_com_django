from django.db import migrations, models
import django.db.models.deletion


# Non-core modules granted to every existing school so their "My Apps" switcher
# keeps showing them. The 'student' module is core and always available, so it
# is intentionally omitted here.
GRANDFATHERED_MODULES = ['grihakarya', 'attendance', 'cas', 'billing', 'calendar']


def grant_modules_to_existing_schools(apps, schema_editor):
    SchoolBranch = apps.get_model('sms', 'SchoolBranch')
    SchoolModuleSubscription = apps.get_model('sms', 'SchoolModuleSubscription')

    rows = [
        SchoolModuleSubscription(school_id=school.id, module_key=key, active=True)
        for school in SchoolBranch.objects.all()
        for key in GRANDFATHERED_MODULES
    ]
    SchoolModuleSubscription.objects.bulk_create(rows, ignore_conflicts=True)


def remove_granted_modules(apps, schema_editor):
    SchoolModuleSubscription = apps.get_model('sms', 'SchoolModuleSubscription')
    SchoolModuleSubscription.objects.filter(module_key__in=GRANDFATHERED_MODULES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0027_schoolbranch_migration_completed_session'),
    ]

    operations = [
        migrations.CreateModel(
            name='SchoolModuleSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('module_key', models.CharField(max_length=50)),
                ('active', models.BooleanField(default=True)),
                ('subscribed_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='module_subscriptions', to='sms.schoolbranch')),
            ],
            options={
                'unique_together': {('school', 'module_key')},
            },
        ),
        migrations.RunPython(grant_modules_to_existing_schools, remove_granted_modules),
    ]
