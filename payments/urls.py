from django.urls import path
from . import views

urlpatterns = [
    path('users/', views.user_list, name='user-list'),
    path('plans/', views.plan_list, name='plan-list'),
    path('subscriptions/me/', views.my_subscription, name='my-subscription'),
    path('subscriptions/cancel/', views.cancel_subscription, name='cancel-subscription'),
    path('subscriptions/change-plan/', views.change_plan, name='change-plan'),
    path('payments/initiate/', views.initiate_payment, name='initiate-payment'),
    path('payments/notify/', views.payment_notify, name='payment-notify'),
    path('payments/return/', views.payment_return, name='payment-return'),
    path('payments/cancel-return/', views.payment_cancel_return, name='payment-cancel-return'),
    path('payments/history/', views.payment_history, name='payment-history'),
]
