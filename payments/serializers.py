from rest_framework import serializers
from .models import Plan


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'tier', 'tier_rank', 'billing_cycle',
            'amount', 'currency', 'payhere_recurrence', 'payhere_duration',
            'features', 'is_active',
        ]
