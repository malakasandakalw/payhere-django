from django.contrib.auth.models import User
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Plan, Subscription
from .serializers import PlanSerializer, SubscriptionSerializer


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
