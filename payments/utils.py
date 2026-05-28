import logging

import requests as http_requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def get_payhere_token():
    token = cache.get('payhere_oauth_token')
    if token:
        logger.info('[PayHere] Using cached OAuth token')
        return token

    logger.info('[PayHere] Fetching new OAuth token from PayHere...')
    response = http_requests.post(
        f"{settings.PAYHERE_BASE_URL}/merchant/v1/oauth/token",
        data={'grant_type': 'client_credentials'},
        auth=(settings.PAYHERE_APP_ID, settings.PAYHERE_APP_SECRET),
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    token = data['access_token']
    expires_in = int(data.get('expires_in', 599))
    cache.set('payhere_oauth_token', token, expires_in - 30)
    logger.info('[PayHere] OAuth token fetched and cached for %d seconds', expires_in - 30)
    return token


def cancel_payhere_subscription(payhere_subscription_id):
    logger.info('[PayHere] Cancelling PayHere subscription: %s', payhere_subscription_id)
    token = get_payhere_token()
    response = http_requests.post(
        f"{settings.PAYHERE_BASE_URL}/merchant/v1/subscription/cancel",
        json={'subscription_id': payhere_subscription_id},
        headers={'Authorization': f'Bearer {token}'},
        timeout=10,
    )
    response.raise_for_status()
    logger.info('[PayHere] Subscription %s cancelled successfully', payhere_subscription_id)
    return response.json()


def retry_payhere_subscription(payhere_subscription_id):
    logger.info('[PayHere] Retrying PayHere subscription charge: %s', payhere_subscription_id)
    token = get_payhere_token()
    response = http_requests.post(
        f"{settings.PAYHERE_BASE_URL}/merchant/v1/subscription/retry",
        json={'subscription_id': payhere_subscription_id},
        headers={'Authorization': f'Bearer {token}'},
        timeout=10,
    )
    response.raise_for_status()
    logger.info('[PayHere] Retry request accepted for subscription %s', payhere_subscription_id)
    return response.json()
