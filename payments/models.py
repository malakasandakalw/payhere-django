import uuid
from django.db import models
from django.contrib.auth.models import User


class Plan(models.Model):
    TIER_CHOICES = [('free', 'Free'), ('pro', 'Pro'), ('enterprise', 'Enterprise')]
    BILLING_CYCLE_CHOICES = [('monthly', 'Monthly'), ('annual', 'Annual')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    tier_rank = models.SmallIntegerField()
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES, blank=True, default='')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default='LKR')
    payhere_recurrence = models.CharField(max_length=20, blank=True, default='')
    payhere_duration = models.CharField(max_length=20, blank=True, default='')
    features = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    pending_plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True, related_name='pending_subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payhere_subscription_id = models.CharField(max_length=100, blank=True, default='')
    customer_token = models.CharField(max_length=200, blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.status})"


class PaymentOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_orders')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='payment_orders')
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_orders')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default='LKR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order_id} - {self.status}"


class PaymentTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.CharField(max_length=100)
    payment_id = models.CharField(max_length=100, unique=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10)
    status_code = models.SmallIntegerField()
    status_message = models.CharField(max_length=255, blank=True, default='')
    payment_method = models.CharField(max_length=30, blank=True, default='')
    card_holder_name = models.CharField(max_length=100, blank=True, default='')
    card_no = models.CharField(max_length=20, blank=True, default='')
    installment_number = models.SmallIntegerField(null=True, blank=True)
    md5sig_verified = models.BooleanField(default=False)
    raw_payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.payment_id} (status: {self.status_code})"


class Refund(models.Model):
    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    INITIATED_BY_CHOICES = [('user', 'User'), ('admin', 'Admin')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_transaction = models.ForeignKey(PaymentTransaction, on_delete=models.PROTECT, related_name='refunds')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='refunds')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='requested')
    initiated_by = models.CharField(max_length=10, choices=INITIATED_BY_CHOICES)
    payhere_refund_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Refund {self.id} - {self.status}"
