from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Plan, Subscription, PaymentTransaction


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


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


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'order_id', 'payment_id', 'amount', 'currency',
            'status_code', 'status_message', 'payment_method',
            'card_holder_name', 'card_no', 'installment_number',
            'md5sig_verified', 'created_at',
        ]
