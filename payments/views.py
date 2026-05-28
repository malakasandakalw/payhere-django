from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Plan
from .serializers import PlanSerializer


@api_view(['GET'])
def plan_list(request):
    plans = Plan.objects.filter(is_active=True).order_by('tier_rank', 'billing_cycle')
    serializer = PlanSerializer(plans, many=True)
    return Response(serializer.data)
