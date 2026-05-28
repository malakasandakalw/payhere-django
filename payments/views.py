import hashlib
import time
from decimal import Decimal, InvalidOperation

import requests as http_requests
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status

from .models import Plan, Subscription, PaymentOrder, PaymentTransaction
from .serializers import PlanSerializer, SubscriptionSerializer, PaymentTransactionSerializer, UserSerializer
from .utils import get_payhere_token, cancel_payhere_subscription

MSG_USER_NOT_FOUND = 'User not found'


@api_view(['GET'])
def user_list(request):
    users = User.objects.filter(is_active=True).order_by('id')
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)


def generate_payhere_hash(merchant_id, order_id, amount, currency, merchant_secret):
    secret_hash = hashlib.md5(merchant_secret.encode()).hexdigest().upper()
    raw = f"{merchant_id}{order_id}{amount}{currency}{secret_hash}"
    return hashlib.md5(raw.encode()).hexdigest().upper()


def verify_notify_md5sig(merchant_id, order_id, payhere_amount, payhere_currency, status_code, merchant_secret, received_md5sig):
    secret_hash = hashlib.md5(merchant_secret.encode()).hexdigest().upper()
    raw = f"{merchant_id}{order_id}{payhere_amount}{payhere_currency}{status_code}{secret_hash}"
    expected = hashlib.md5(raw.encode()).hexdigest().upper()
    return expected == received_md5sig.upper()


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
        return Response({'error': MSG_USER_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

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
        return Response({'error': MSG_USER_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

    try:
        plan = Plan.objects.get(pk=plan_id, is_active=True)
    except Plan.DoesNotExist:
        return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)

    if plan.tier == 'free':
        return Response({'error': 'Cannot initiate payment for the free plan'}, status=status.HTTP_400_BAD_REQUEST)

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


def _resolve_context(data):
    """Extract user, plan, subscription from a notify payload."""
    payment_order = PaymentOrder.objects.filter(order_id=data['order_id']).first()
    if payment_order:
        return payment_order.user, payment_order.plan, payment_order.subscription, payment_order

    payhere_subscription_id = data.get('subscription_id', '')
    if payhere_subscription_id:
        subscription = Subscription.objects.filter(
            payhere_subscription_id=payhere_subscription_id
        ).first()
        if subscription:
            return subscription.user, subscription.plan, subscription, None

    return None, None, None, None


def _activate_subscription(user, plan, payment_order, transaction, payhere_subscription_id, customer_token):
    period_start = now()
    period_end = period_start + (relativedelta(years=1) if plan.billing_cycle == 'annual' else relativedelta(months=1))

    free_plan = Plan.objects.get(tier='free')
    subscription, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={'plan': free_plan, 'status': 'pending'},
    )
    subscription.plan = plan
    subscription.status = 'active'
    subscription.payhere_subscription_id = payhere_subscription_id
    if customer_token:
        subscription.customer_token = customer_token
    if not subscription.started_at:
        subscription.started_at = period_start
    subscription.current_period_start = period_start
    subscription.current_period_end = period_end
    subscription.save()

    if payment_order:
        payment_order.status = 'completed'
        payment_order.subscription = subscription
        payment_order.save()

    transaction.subscription = subscription
    transaction.save()


def _handle_failed_charge(subscription, payment_order):
    from datetime import timedelta
    if subscription:
        subscription.status = 'failed'
        subscription.grace_period_end = now() + timedelta(days=4)
        subscription.retry_count = 0
        subscription.save()
        from django.core.mail import send_mail
        from django.conf import settings as django_settings
        send_mail(
            subject='Action required: Your payment failed',
            message=(
                f"Hi {subscription.user.first_name},\n\n"
                f"Your payment for {subscription.plan.name} failed. "
                f"We will automatically retry for the next 4 days.\n\n"
                f"If retries fail, your account will move to the Free plan. "
                f"You can also resubscribe manually from the pricing page.\n\n"
                f"Team Vertext"
            ),
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.user.email],
            fail_silently=True,
        )
    if payment_order:
        payment_order.status = 'failed'
        payment_order.save()


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def payment_notify(request):
    # Always return HTTP 200 — any other status causes PayHere to retry indefinitely
    data = request.data

    payment_id = data.get('payment_id', '')
    status_code_raw = data.get('status_code', '0')

    try:
        status_code_int = int(status_code_raw)
    except (ValueError, TypeError):
        status_code_int = 0

    try:
        amount_decimal = Decimal(data.get('payhere_amount', '0'))
    except InvalidOperation:
        amount_decimal = Decimal('0.00')

    try:
        install_number = int(data.get('item_rec_install_paid')) if data.get('item_rec_install_paid') else None
    except (ValueError, TypeError):
        install_number = None

    if PaymentTransaction.objects.filter(payment_id=payment_id).exists():
        return Response({'status': 'already processed'})

    merchant_id = data.get('merchant_id', '')
    order_id = data.get('order_id', '')
    payhere_amount = data.get('payhere_amount', '')
    payhere_currency = data.get('payhere_currency', '')
    received_md5sig = data.get('md5sig', '')
    payhere_subscription_id = data.get('subscription_id', '')
    customer_token = data.get('customer_token', '')

    md5sig_verified = verify_notify_md5sig(
        merchant_id, order_id, payhere_amount, payhere_currency,
        status_code_raw, settings.PAYHERE_MERCHANT_SECRET, received_md5sig,
    )

    user, plan, subscription, payment_order = _resolve_context(data)
    if user is None:
        return Response({'status': 'ok'})

    transaction = PaymentTransaction.objects.create(
        order_id=order_id,
        payment_id=payment_id,
        subscription=subscription,
        user=user,
        amount=amount_decimal,
        currency=payhere_currency,
        status_code=status_code_int,
        status_message=data.get('status_message', ''),
        payment_method=data.get('method', ''),
        card_holder_name=data.get('card_holder_name', ''),
        card_no=data.get('card_no', ''),
        installment_number=install_number,
        md5sig_verified=md5sig_verified,
        raw_payload=dict(data),
    )

    if md5sig_verified and status_code_int == 2:
        _activate_subscription(user, plan, payment_order, transaction, payhere_subscription_id, customer_token)
    elif md5sig_verified and status_code_int == -2:
        _handle_failed_charge(subscription, payment_order)
    elif payment_order and status_code_int == -1:
        payment_order.status = 'cancelled'
        payment_order.save()

    return Response({'status': 'ok'})


# ---------------------------------------------------------------------------
# Step 7: Cancel subscription
# ---------------------------------------------------------------------------

@api_view(['POST'])
def cancel_subscription(request):
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': MSG_USER_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

    try:
        subscription = Subscription.objects.get(user=user)
    except Subscription.DoesNotExist:
        return Response({'error': 'No subscription found'}, status=status.HTTP_404_NOT_FOUND)

    if subscription.status != 'active':
        return Response({'error': 'Subscription is not active'}, status=status.HTTP_400_BAD_REQUEST)

    if subscription.cancel_at_period_end:
        return Response({'error': 'Subscription is already scheduled for cancellation'}, status=status.HTTP_400_BAD_REQUEST)

    if not subscription.payhere_subscription_id:
        return Response({'error': 'No PayHere subscription ID found'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        cancel_payhere_subscription(subscription.payhere_subscription_id)
    except http_requests.RequestException as exc:
        return Response({'error': f'PayHere API error: {exc}'}, status=status.HTTP_502_BAD_GATEWAY)

    subscription.cancel_at_period_end = True
    subscription.cancelled_at = now()
    subscription.save()

    serializer = SubscriptionSerializer(subscription)
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# Step 8: Change plan
# ---------------------------------------------------------------------------

def _is_upgrade(current_plan, new_plan):
    if new_plan.tier_rank > current_plan.tier_rank:
        return True
    if (new_plan.tier_rank == current_plan.tier_rank
            and new_plan.billing_cycle == 'annual'
            and current_plan.billing_cycle == 'monthly'):
        return True
    return False


@api_view(['POST'])
def change_plan(request):
    user_id = request.data.get('user_id')
    new_plan_id = request.data.get('new_plan_id')

    if not user_id or not new_plan_id:
        return Response({'error': 'user_id and new_plan_id are required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': MSG_USER_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

    try:
        subscription = Subscription.objects.get(user=user)
    except Subscription.DoesNotExist:
        return Response({'error': 'No subscription found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        new_plan = Plan.objects.get(pk=new_plan_id, is_active=True)
    except Plan.DoesNotExist:
        return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)

    if new_plan.tier == 'free':
        return Response({'error': 'Use the cancel endpoint to move to the free plan'}, status=status.HTTP_400_BAD_REQUEST)

    if subscription.plan == new_plan:
        return Response({'error': 'User is already on this plan'}, status=status.HTTP_400_BAD_REQUEST)

    direction = 'upgrade' if _is_upgrade(subscription.plan, new_plan) else 'downgrade'
    subscription.pending_plan = new_plan
    subscription.save()

    serializer = SubscriptionSerializer(subscription)
    return Response({
        'direction': direction,
        'message': f'Plan change to {new_plan.name} scheduled. Takes effect at end of current period.',
        'subscription': serializer.data,
    })


# ---------------------------------------------------------------------------
# Step 9: Payment history
# ---------------------------------------------------------------------------

@api_view(['GET'])
def payment_history(request):
    user_id = request.query_params.get('user_id')
    if not user_id:
        return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': MSG_USER_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

    transactions = PaymentTransaction.objects.filter(user=user).order_by('-created_at')
    serializer = PaymentTransactionSerializer(transactions, many=True)
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# Step 10: Return and cancel-return URL handlers
# ---------------------------------------------------------------------------

@api_view(['GET'])
def payment_return(request):
    # PayHere redirects the user's browser here after payment.
    # No payment data is passed — Angular polls /api/subscriptions/me/ to get the result.
    return Response({'message': 'Payment flow complete. Check subscription status.'})


@api_view(['GET'])
def payment_cancel_return(request):
    # PayHere redirects here when the user leaves without paying.
    order_id = request.query_params.get('order_id', '')
    if order_id:
        PaymentOrder.objects.filter(order_id=order_id, status='pending').update(status='cancelled')
    return Response({'message': 'Payment cancelled by user.'})
