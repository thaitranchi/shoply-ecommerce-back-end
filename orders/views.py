from django.db import transaction
from django.urls import reverse
from rest_framework import generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Order
from .serializers import OrderSerializer, PaymentSerializer,\
     CancellationSerializer, PaymentSerializer
import stripe
from rest_framework.views import APIView
from django.conf import settings

# Set your Stripe secret key
stripe.api_key = settings.STRIPE_SECRET_KEY

# ✅ Pagination for orders
class OrderPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

# ✅ List all orders for the authenticated user
class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = OrderPagination

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by('-created_at')

# ✅ Create a new order with transaction management
class OrderCreateView(generics.CreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()  # ✅ No need to pass user explicitly

# ✅ Retrieve and update order details
class OrderDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def partial_update(self, request, *args, **kwargs):
        allowed_fields = {'status', 'is_paid'}
        if set(request.data.keys()) - allowed_fields:
            return Response({"detail": "Only status and is_paid can be updated."}, status=400)
        response = super().partial_update(request, *args, **kwargs)
        return Response(response.data, status=202)

class PaymentView(APIView):
    def post(self, request):
        serializer = PaymentSerializer(data=request.data)
        if serializer.is_valid():
            order_id = serializer.validated_data['order_id']
            token = serializer.validated_data['token']
            order = Order.objects.get(id=order_id)

            try:
                # Create Stripe charge
                charge = stripe.Charge.create(
                    amount=int(order.total_price * 100),  # Convert to cents
                    currency='usd',
                    description=f'Order #{order.id}',
                    source=token,
                )

                # Update order on success
                order.payment_id = charge["id"]
                order.payment_status = 'paid'
                order.is_paid = True
                order.status = 'processing'  # Auto-move to processing
                order.save()

                return Response({'message': 'Payment successful', 'payment_id': charge["id"]}, status=status.HTTP_200_OK)

            except stripe.error.StripeError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        serializer = self.get_serializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        if serializer.validated_data.get('payment_status') == 'success':
            serializer.save(is_paid=True)
        else:
            serializer.save(is_paid=False)
        
        return Response(serializer.data, status=status.HTTP_200_OK)

class CancellationView(generics.UpdateAPIView):
    queryset = Order.objects.all()
    serializer_class = CancellationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        order = self.get_object()

        if order.status == 'delivered':
            return Response({"error": "Delivered orders cannot be cancelled."},
                            status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)