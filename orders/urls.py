from django.urls import path
from .views import OrderListView, OrderCreateView, \
    OrderDetailView, PaymentView, CancellationView

urlpatterns = [
    path('', OrderListView.as_view(), name='order-list'),
    path('create/', OrderCreateView.as_view(), name='order-create'),
    path('<int:pk>/', OrderDetailView.as_view(), name='order-detail'),
    path('orders/<int:pk>/payment/', PaymentView.as_view(), name='order-payment'),
    path('orders/<int:pk>/cancel/', CancellationView.as_view(), name='order-cancellation'),
    path('payments/', PaymentView.as_view(), name='order-payment'),
]
