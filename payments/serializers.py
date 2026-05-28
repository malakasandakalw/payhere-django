from rest_framework import serializers
from .models import Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'tier', 'tier_rank', 'billing_cycle',
            'amount', 'currency', 'payhere_recurrence', 'payhere_duration',
            'features', 'is_active',
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    pending_plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'pending_plan', 'status',
            'started_at', 'current_period_start', 'current_period_end',
            'cancelled_at', 'cancel_at_period_end',
        ]
