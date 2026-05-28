from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils.timezone import now

from .models import Plan, Subscription
from .utils import cancel_payhere_subscription


@shared_task
def expire_cancelled_subscriptions():
    """
    Runs daily at midnight.
    Finds subscriptions where the user cancelled and the paid period has now ended.
    Moves them to expired and drops the user back to the Free plan.
    """
    subscriptions = Subscription.objects.filter(
        cancel_at_period_end=True,
        current_period_end__lte=now(),
        status='active',
    ).select_related('user', 'plan')

    free_plan = Plan.objects.get(tier='free')
    count = 0

    for subscription in subscriptions:
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
                f"Team Vertext"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.user.email],
            fail_silently=True,
        )
        count += 1

    return f'{count} subscription(s) expired and moved to Free plan'


@shared_task
def activate_pending_plan_changes():
    """
    Runs daily at midnight.
    Finds subscriptions where the user requested a plan change and the current period has ended.
    Cancels the old PayHere subscription and notifies the user to complete payment for the new plan.
    """
    subscriptions = Subscription.objects.filter(
        pending_plan__isnull=False,
        current_period_end__lte=now(),
        status='active',
    ).select_related('user', 'plan', 'pending_plan')

    count = 0

    for subscription in subscriptions:
        new_plan = subscription.pending_plan

        if subscription.payhere_subscription_id:
            try:
                cancel_payhere_subscription(subscription.payhere_subscription_id)
            except Exception:
                pass

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
                f"Team Vertext"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.user.email],
            fail_silently=True,
        )
        count += 1

    return f'{count} pending plan change(s) processed'


@shared_task
def send_renewal_reminders():
    """
    Runs daily at 9am.
    Sends a reminder email to users whose subscription renews in exactly 3 days.
    No action needed from the user — PayHere auto-charges their saved card.
    """
    reminder_date = (now() + timedelta(days=3)).date()

    subscriptions = Subscription.objects.filter(
        status='active',
        cancel_at_period_end=False,
        current_period_end__date=reminder_date,
    ).select_related('user', 'plan')

    count = 0

    for subscription in subscriptions:
        renewal_date = subscription.current_period_end.strftime('%B %d, %Y')
        send_mail(
            subject=f'Your {subscription.plan.name} renews in 3 days',
            message=(
                f"Hi {subscription.user.first_name},\n\n"
                f"Just a heads-up — your {subscription.plan.name} subscription renews on {renewal_date}.\n\n"
                f"LKR {subscription.plan.amount} will be automatically charged to your saved card. "
                f"No action needed.\n\n"
                f"To cancel before renewal, visit your billing page.\n\n"
                f"Team Vertext"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.user.email],
            fail_silently=True,
        )
        count += 1

    return f'{count} renewal reminder(s) sent'


@shared_task
def alert_failed_subscriptions():
    """
    Runs daily at 9am.
    Sends a warning email to users whose recurring payment has failed.
    """
    subscriptions = Subscription.objects.filter(
        status='failed',
    ).select_related('user', 'plan')

    count = 0

    for subscription in subscriptions:
        send_mail(
            subject='Action required: Your payment failed',
            message=(
                f"Hi {subscription.user.first_name},\n\n"
                f"Your last payment for {subscription.plan.name} failed and your access "
                f"may be restricted.\n\n"
                f"Please visit the pricing page to resubscribe with an updated payment method.\n\n"
                f"If you believe this is a mistake, contact our support team.\n\n"
                f"Team Vertext"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.user.email],
            fail_silently=True,
        )
        count += 1

    return f'{count} failed subscription alert(s) sent'
