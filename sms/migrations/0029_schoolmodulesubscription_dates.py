import calendar
import datetime

from django.db import migrations, models


def _add_months(d, months):
    """Return ``d`` shifted forward by ``months`` (day clamped to month length)."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def backfill_subscription_dates(apps, schema_editor):
    """Give existing subscriptions a start date and a 12-month expiry."""
    SchoolModuleSubscription = apps.get_model('sms', 'SchoolModuleSubscription')
    for sub in SchoolModuleSubscription.objects.all():
        start = sub.subscribed_at.date() if sub.subscribed_at else datetime.date.today()
        sub.starts_on = start
        sub.expires_on = _add_months(start, 12)
        sub.save(update_fields=['starts_on', 'expires_on'])


def clear_subscription_dates(apps, schema_editor):
    SchoolModuleSubscription = apps.get_model('sms', 'SchoolModuleSubscription')
    SchoolModuleSubscription.objects.update(starts_on=None, expires_on=None)


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0028_schoolmodulesubscription'),
    ]

    operations = [
        migrations.AddField(
            model_name='schoolmodulesubscription',
            name='starts_on',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='schoolmodulesubscription',
            name='expires_on',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_subscription_dates, clear_subscription_dates),
    ]
