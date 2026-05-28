from django.db import migrations


def seed_plans(apps, schema_editor):
    plan_model = apps.get_model('payments', 'Plan')

    plans = [
        {
            'name': 'Free',
            'tier': 'free',
            'tier_rank': 0,
            'billing_cycle': '',
            'amount': '0.00',
            'currency': 'LKR',
            'payhere_recurrence': '',
            'payhere_duration': '',
            'features': {'max_users': 1, 'storage_gb': 1, 'api_calls': 100},
            'is_active': True,
        },
        {
            'name': 'Pro Monthly',
            'tier': 'pro',
            'tier_rank': 1,
            'billing_cycle': 'monthly',
            'amount': '2500.00',
            'currency': 'LKR',
            'payhere_recurrence': '1 Month',
            'payhere_duration': 'Forever',
            'features': {'max_users': 10, 'storage_gb': 50, 'api_calls': 10000},
            'is_active': True,
        },
        {
            'name': 'Pro Annual',
            'tier': 'pro',
            'tier_rank': 1,
            'billing_cycle': 'annual',
            'amount': '25000.00',
            'currency': 'LKR',
            'payhere_recurrence': '1 Year',
            'payhere_duration': 'Forever',
            'features': {'max_users': 10, 'storage_gb': 50, 'api_calls': 10000},
            'is_active': True,
        },
        {
            'name': 'Enterprise Monthly',
            'tier': 'enterprise',
            'tier_rank': 2,
            'billing_cycle': 'monthly',
            'amount': '8000.00',
            'currency': 'LKR',
            'payhere_recurrence': '1 Month',
            'payhere_duration': 'Forever',
            'features': {'max_users': 100, 'storage_gb': 500, 'api_calls': 100000},
            'is_active': True,
        },
        {
            'name': 'Enterprise Annual',
            'tier': 'enterprise',
            'tier_rank': 2,
            'billing_cycle': 'annual',
            'amount': '80000.00',
            'currency': 'LKR',
            'payhere_recurrence': '1 Year',
            'payhere_duration': 'Forever',
            'features': {'max_users': 100, 'storage_gb': 500, 'api_calls': 100000},
            'is_active': True,
        },
    ]

    for plan in plans:
        plan_model.objects.get_or_create(name=plan['name'], defaults=plan)


def delete_plans(apps, schema_editor):
    plan_model = apps.get_model('payments', 'Plan')
    plan_model.objects.filter(name__in=[
        'Free', 'Pro Monthly', 'Pro Annual',
        'Enterprise Monthly', 'Enterprise Annual',
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_plans, delete_plans),
    ]
