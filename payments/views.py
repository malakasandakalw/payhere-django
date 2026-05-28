import hashlib
import time

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import Plan, Subscription, PaymentOrder
from .serializers import PlanSerializer, SubscriptionSerializer


def generate_payhere_hash(merchant_id, order_id, amount, currency, merchant_secret):
    secret_hash = hashlib.md5(merchant_secret.encode()).hexdigest().upper()
    raw = f"{merchant_id}{order_id}{amount}{currency}{secret_hash}"
    return hashlib.md5(raw.encode()).hexdigest().upper()


@api_view(['GET'])
def plan_list(request):
    plans = Plan.objects.filter(is_active=True).order_by('tier_rank', 'billing_cycle')
    serializer = PlanSerializer(plans, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def my_subscription(request):
    user_id = request.query_params.get('user_id')
    if not user_id:
        return Response({'error': 'user_id query parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    free_plan = Plan.objects.get(tier='free')
    subscription, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={'plan': free_plan, 'status': 'active'},
    )

    serializer = SubscriptionSerializer(subscription)
    return Response(serializer.data)


@api_view(['POST'])
def initiate_payment(request):
    user_id = request.data.get('user_id')
    plan_id = request.data.get('plan_id')

    if not user_id or not plan_id:
        return Response(
            {'error': 'user_id and plan_id are required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        plan = Plan.objects.get(pk=plan_id, is_active=True)
    except Plan.DoesNotExist:
        return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)

    if plan.tier == 'free':
        return Response({'error': 'Cannot initiate payment for the free plan'}, status=status.HTTP_400_BAD_REQUEST)

    # Block if this user already has a pending payment order
    if PaymentOrder.objects.filter(user=user, status='pending').exists():
        return Response(
            {'error': 'A payment is already in progress for this user'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    order_id = f"ORD-{user.id}-{int(time.time())}"
    amount = f"{plan.amount:.2f}"
    currency = plan.currency

    PaymentOrder.objects.create(
        order_id=order_id,
        user=user,
        plan=plan,
        amount=plan.amount,
        currency=currency,
        status='pending',
    )

    payhere_hash = generate_payhere_hash(
        settings.PAYHERE_MERCHANT_ID,
        order_id,
        amount,
        currency,
        settings.PAYHERE_MERCHANT_SECRET,
    )

    return Response({
        'merchant_id': settings.PAYHERE_MERCHANT_ID,
        'return_url': settings.PAYHERE_RETURN_URL,
        'cancel_url': settings.PAYHERE_CANCEL_URL,
        'notify_url': settings.PAYHERE_NOTIFY_URL,
        'order_id': order_id,
        'items': plan.name,
        'currency': currency,
        'amount': amount,
        'first_name': user.first_name or user.username,
        'last_name': user.last_name or '',
        'email': user.email,
        'phone': '0771234567',
        'address': 'No. 1, Test Street',
        'city': 'Colombo',
        'country': 'Sri Lanka',
        'hash': payhere_hash,
        'recurrence': plan.payhere_recurrence,
        'duration': plan.payhere_duration,
    })
