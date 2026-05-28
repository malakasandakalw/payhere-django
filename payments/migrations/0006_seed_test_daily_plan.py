from django.db import migrations


def seed_test_daily_plan(apps, schema_editor):
    Plan = apps.get_model('payments', 'Plan')
    Plan.objects.get_or_create(
        name='Test Daily',
        defaults={
            'tier': 'pro',
            'tier_rank': 1,
            'billing_cycle': 'daily',
            'amount': '100.00',
            'currency': 'LKR',
            'payhere_recurrence': '1 Day',
            'payhere_duration': 'Forever',
            'features': {'max_users': 10, 'storage_gb': 50, 'api_calls': 10000},
            'is_active': True,
        }
    )


def delete_test_daily_plan(apps, schema_editor):
    Plan = apps.get_model('payments', 'Plan')
    Plan.objects.filter(name='Test Daily').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0005_alter_plan_billing_cycle'),
    ]

    operations = [
        migrations.RunPython(seed_test_daily_plan, delete_test_daily_plan),
    ]
