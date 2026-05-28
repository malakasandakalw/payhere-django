import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils.timezone import now

from .models import Plan, Subscription
from .utils import cancel_payhere_subscription, retry_payhere_subscription

logger = logging.getLogger(__name__)


@shared_task
def expire_cancelled_subscriptions():
    """
    Runs daily at midnight.
    Finds subscriptions where the user cancelled and the paid period has now ended.
    Moves them to expired and drops the user back to the Free plan.
    """
    logger.info('[Task] expire_cancelled_subscriptions: starting')
    subscriptions = Subscription.objects.filter(
        cancel_at_period_end=True,
        current_period_end__lte=now(),
        status='active',
    ).select_related('user', 'plan')

    free_plan = Plan.objects.get(tier='free')
    count = 0

    for subscription in subscriptions:
        logger.info('[Task] Expiring cancelled subscription | user=%s plan="%s"',
                    subscription.user.username, subscription.plan.name)
        subscription.status = 'expired'
        subscription.plan = free_plan
        subscription.cancel_at_period_end = False
        subscription.save()

        send_mail(
            subject='Your subscription has ended',
            message=(
                f"Hi {subscription.user.first_name},\n\n"
                f"Your subscription has ended and you have been moved to the Free plan.\n\n"
                f"To resubscribe, visit the pricing page.\n\n"
                f"Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.user.email],
            fail_silently=True,
        )
        count += 1

    result = f'{count} subscription(s) expired and moved to Free plan'
    logger.info('[Task] expire_cancelled_subscriptions: done — %s', result)
    return result


@shared_task
def activate_pending_plan_changes():
    """
    Runs daily at midnight.
    Finds subscriptions where the user requested a plan change and the current period has ended.
    Cancels the old PayHere subscription and notifies the user to complete payment for the new plan.
    """
    logger.info('[Task] activate_pending_plan_changes: starting')
    subscriptions = Subscription.objects.filter(
        pending_plan__isnull=False,
        current_period_end__lte=now(),
        status='active',
    ).select_related('user', 'plan', 'pending_plan')

    count = 0

    for subscription in subscriptions:
        new_plan = subscription.pending_plan
        logger.info('[Task] Activating plan change | user=%s old="%s" new="%s"',
                    subscription.user.username, subscription.plan.name, new_plan.name)

        if subscription.payhere_subscription_id:
            try:
                cancel_payhere_subscription(subscription.payhere_subscription_id)
            except Exception:
                logger.warning('[Task] Failed to cancel PayHere subscription %s — continuing anyway',
                               subscription.payhere_subscription_id)

        subscription.plan = new_plan
        subscription.pending_plan = None
        subscription.status = 'pending'
        subscription.payhere_subscription_id = ''
        subscription.current_period_start = None
        subscription.current_period_end = None
        subscription.save()

        send_mail(
            subject=f'Your {new_plan.name} plan is ready to activate',
            message=(
                f"Hi {subscription.user.first_name},\n\n"
                f"Your current plan has ended. Your requested {new_plan.name} plan is ready.\n\n"
                f"Please visit the pricing page and complete the payment to activate it.\n\n"
                f"Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.user.email],
            fail_silently=True,
        )
        count += 1

    result = f'{count} pending plan change(s) processed'
    logger.info('[Task] activate_pending_plan_changes: done — %s', result)
    return result


@shared_task
def send_renewal_reminders():
    """
    Runs daily at 9am.
    Sends a reminder email to users whose subscription renews in exactly 3 days.
    No action needed from the user — PayHere auto-charges their saved card.
    """
    logger.info('[Task] send_renewal_reminders: starting')
    reminder_date = (now() + timedelta(days=3)).date()

    subscriptions = Subscription.objects.filter(
        status='active',
        cancel_at_period_end=False,
        current_period_end__date=reminder_date,
    ).select_related('user', 'plan')

    count = 0

    for subscription in subscriptions:
        renewal_date = subscription.current_period_end.strftime('%B %d, %Y')
        logger.info('[Task] Sending renewal reminder | user=%s plan="%s" renewal=%s',
                    subscription.user.username, subscription.plan.name, renewal_date)
        send_mail(
            subject=f'Your {subscription.plan.name} renews in 3 days',
            message=(
                f"Hi {subscription.user.first_name},\n\n"
                f"Just a heads-up — your {subscription.plan.name} subscription renews on {renewal_date}.\n\n"
                f"LKR {subscription.plan.amount} will be automatically charged to your saved card. "
                f"No action needed.\n\n"
                f"To cancel before renewal, visit your billing page.\n\n"
                f"Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.user.email],
            fail_silently=True,
        )
        count += 1

    result = f'{count} renewal reminder(s) sent'
    logger.info('[Task] send_renewal_reminders: done — %s', result)
    return result


@shared_task
def alert_failed_subscriptions():
    """
    Runs daily at 9am.
    Sends a warning email to users whose recurring payment has failed.
    """
    logger.info('[Task] alert_failed_subscriptions: starting')
    subscriptions = Subscription.objects.filter(
        status='failed',
    ).select_related('user', 'plan')

    count = 0

    for subscription in subscriptions:
        logger.info('[Task] Alerting failed subscription | user=%s plan="%s" retry_count=%d',
                    subscription.user.username, subscription.plan.name, subscription.retry_count)
        send_mail(
            subject='Action required: Your payment failed',
            message=(
                f"Hi {subscription.user.first_name},\n\n"
                f"Your last payment for {subscription.plan.name} failed and your access "
                f"may be restricted.\n\n"
                f"Please visit the pricing page to resubscribe with an updated payment method.\n\n"
                f"If you believe this is a mistake, contact our support team.\n\n"
                f"Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.user.email],
            fail_silently=True,
        )
        count += 1

    result = f'{count} failed subscription alert(s) sent'
    logger.info('[Task] alert_failed_subscriptions: done — %s', result)
    return result


@shared_task
def process_dunning_retries():
    """
    Runs daily at 10am.
    For every failed subscription still within the grace period:
      - Calls PayHere retry API
      - If PayHere accepts the retry, increments retry_count and waits for notify_url result
      - If grace period has expired, moves user to Free plan and sends final email
    Note: The actual success/failure of the retry charge comes back via notify_url callback.
    """
    logger.info('[Task] process_dunning_retries: starting')
    free_plan = Plan.objects.get(tier='free')
    subscriptions = Subscription.objects.filter(
        status='failed',
        grace_period_end__isnull=False,
    ).select_related('user', 'plan')

    retried = 0
    expired = 0

    for subscription in subscriptions:
        if now() > subscription.grace_period_end:
            logger.warning('[Task] Grace period expired | user=%s plan="%s" — moving to Free plan',
                           subscription.user.username, subscription.plan.name)
            subscription.status = 'expired'
            subscription.plan = free_plan
            subscription.grace_period_end = None
            subscription.retry_count = 0
            subscription.save()
            send_mail(
                subject='Your subscription has been cancelled due to payment failure',
                message=(
                    f"Hi {subscription.user.first_name},\n\n"
                    f"We tried to charge your card for {subscription.plan.name} several times "
                    f"but were unable to process the payment.\n\n"
                    f"Your account has been moved to the Free plan.\n\n"
                    f"To resubscribe, visit the pricing page and complete a new payment.\n\n"
                    f"Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[subscription.user.email],
                fail_silently=True,
            )
            expired += 1
            continue

        if not subscription.payhere_subscription_id:
            logger.warning('[Task] Skipping retry — no payhere_subscription_id | user=%s',
                           subscription.user.username)
            continue

        try:
            retry_payhere_subscription(subscription.payhere_subscription_id)
            subscription.retry_count += 1
            subscription.save()
            logger.info('[Task] Retry attempt %d sent | user=%s sub=%s',
                        subscription.retry_count, subscription.user.username,
                        subscription.payhere_subscription_id)
            retried += 1
        except Exception:
            logger.exception('[Task] Retry API call failed | user=%s sub=%s',
                             subscription.user.username, subscription.payhere_subscription_id)

    result = f'{retried} retry attempt(s) made, {expired} subscription(s) expired after grace period'
    logger.info('[Task] process_dunning_retries: done — %s', result)
    return result
