from django.urls import path
from . import views

urlpatterns = [
    path('plans/', views.plan_list, name='plan-list'),
    path('subscriptions/me/', views.my_subscription, name='my-subscription'),
    path('payments/initiate/', views.initiate_payment, name='initiate-payment'),
    path('payments/notify/', views.payment_notify, name='payment-notify'),
]
