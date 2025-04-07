from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from products.models import Product
from .models import Order, OrderItem, OrderStatusHistory
from unittest import mock
from django.test import TestCase
import stripe

User = get_user_model()

class OrderModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.product = Product.objects.create(name='Test Product', price=100.00, stock=10)
        self.order = Order.objects.create(user=self.user)

    def test_order_item_stock_reduction(self):
        """Ensure stock is reduced when an OrderItem is created."""
        OrderItem.objects.create(order=self.order, product=self.product, quantity=2, price=100.00)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    def test_order_total_price_auto_update(self):
        """Ensure total price updates automatically on item addition."""
        OrderItem.objects.create(order=self.order, product=self.product, quantity=2, price=100.00)
        self.order.refresh_from_db()
        self.assertEqual(float(self.order.total_price), 200.00)

    def test_stock_rollback_on_failure(self):
        """Ensure stock is rolled back if transaction fails."""
        try:
            with transaction.atomic():
                OrderItem.objects.create(order=self.order, product=self.product, quantity=20, price=100.00)
        except Exception:
            pass

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_order_status_history_tracking(self):
        """Ensure status changes are tracked in OrderStatusHistory."""
        self.order.status = 'shipped'
        self.order.save()

        history = OrderStatusHistory.objects.filter(order=self.order).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.previous_status, 'pending')
        self.assertEqual(history.new_status, 'shipped')

class OrderAPITests(APITestCase):

    def setUp(self):
        # ✅ Create a test user
        self.user = User.objects.create_user(
            username='testuser', 
            email='testuser@example.com',
            password='testpassword'
        )
        self.client.force_authenticate(user=self.user)

        # ✅ Create sample products
        self.product1 = Product.objects.create(
            name="Product 1", description="Description 1", price=100.00, stock=10
        )
        self.product2 = Product.objects.create(
            name="Product 2", description="Description 2", price=200.00, stock=5
        )

        # ✅ Define URLs
        self.order_list_url = reverse('order-list')  # Ensure correct URL names
        self.order_create_url = reverse('order-create')

    # ✅ Test order creation with multiple items
    def test_create_order(self):
        data = {
            "items": [
                {"product": self.product1.id, "quantity": 2, "price": 100.00},
                {"product": self.product2.id, "quantity": 1, "price": 200.00}
            ]
        }
        response = self.client.post(self.order_create_url, data, format='json')
        print("Create Order Response:", response.status_code, response.data)  # ✅ Debug output
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data['items']), 2)

    # ✅ Test insufficient stock scenario
    def test_create_order_insufficient_stock(self):
        data = {
            "items": [{"product": self.product2.id, "quantity": 10, "price": "200.00"}]
        }
        response = self.client.post(self.order_create_url, data, format='json')
        print("Insufficient Stock Response:", response.status_code, response.data)  # ✅ Debug output
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient stock for Product 2', str(response.data))

    def test_create_order_invalid_data(self):
        # No items provided
        data = {}
        response = self.client.post(self.order_create_url, data, format='json')
        print("Invalid Data Response:", response.status_code, response.data)  # ✅ Debug output
        # Check for the correct system-generated validation error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("This field is required.", str(response.data))

    def test_update_order_status(self):
        order = Order.objects.create(user=self.user, total_price=300.00)
        order_detail_url = reverse('order-detail', kwargs={'pk': order.id})

        response = self.client.patch(order_detail_url, {'status': 'shipped'}, format='json')
        print("Update Status Response:", response.status_code, response.data)  # ✅ Debug output
        # If 202 is expected, adjust the assertion
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['status'], 'shipped')

    class PaymentTests(APITestCase):

        def setUp(self):
            self.user = User.objects.create_user(
                username='testuser', 
                password='testpassword'
            )
            self.client.force_authenticate(user=self.user)
            self.order = Order.objects.create(user=self.user, total_price=500.00)

        def test_successful_payment(self):
            url = reverse('order-payment', kwargs={'pk': self.order.id})
            data = {
                "payment_id": "PAY123456",
                "payment_status": "success"
            }
            response = self.client.patch(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['is_paid'])
            self.assertEqual(response.data['payment_status'], "success")

        def test_failed_payment(self):
            url = reverse('order-payment', kwargs={'pk': self.order.id})
            data = {
                "payment_id": "PAY654321",
                "payment_status": "failure"
            }
            response = self.client.patch(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertFalse(response.data['is_paid'])
            self.assertEqual(response.data['payment_status'], "failure")

class CancellationTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword'
        )
        self.client.force_authenticate(user=self.user)
        self.order = Order.objects.create(
            user=self.user,
            total_price=300.00,
            status='pending',
            is_paid=True,
            payment_id='PAY123456',
            payment_status='success'
        )
        self.cancel_url = reverse('order-cancellation', kwargs={'pk': self.order.id})

    def test_cancel_order_success(self):
        data = {"status": "cancelled"}
        response = self.client.patch(self.cancel_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_refunded'])
        self.assertEqual(response.data['refund_id'], f"REF-{self.order.id}")

    def test_cancel_already_delivered_order(self):
        self.order.status = 'delivered'
        self.order.save()
        data = {"status": "cancelled"}
        response = self.client.patch(self.cancel_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Delivered orders cannot be cancelled.", str(response.data))

class PaymentAPITests(APITestCase):

    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpassword'
        )
        self.client.force_authenticate(user=self.user)

        # Create sample product
        self.product = Product.objects.create(
            name="Test Product", description="Test Description", price=100.00, stock=10
        )

        # Create an unpaid order
        self.order = Order.objects.create(
            user=self.user,
            total_price=300.00,
            is_paid=False,
            status='pending'
        )

        # Define payment URL
        self.payment_url = reverse('order-payment')

    @mock.patch('stripe.Charge.create')
    def test_successful_payment(self, mock_charge):
        mock_charge.return_value = {
            "id": "ch_12345",
            "amount": 30000,
            "currency": "usd",
            "status": "succeeded"
        }

        data = {"order_id": self.order.id, "token": "tok_visa"}
        response = self.client.post(self.payment_url, data, format='json')

        self.order.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.order.is_paid)
        self.assertEqual(self.order.payment_id, "ch_12345")

    @mock.patch('stripe.Charge.create')
    def test_failed_payment_due_to_stripe_error(self, mock_charge):
        mock_charge.side_effect = stripe.error.StripeError("Payment failed")
        
        data = {"order_id": self.order.id, "token": "tok_visa"}
        response = self.client.post(self.payment_url, data, format='json')
        
        self.order.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(self.order.is_paid)
        self.assertIn("Payment failed", str(response.data))

    def test_payment_with_invalid_order(self):
        # Invalid order ID
        data = {
            "order_id": 9999,
            "token": "tok_visa"
        }
        response = self.client.post(self.payment_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Order not found or already paid.", str(response.data))

    def test_payment_already_paid_order(self):
        # Mark order as paid
        self.order.is_paid = True
        self.order.payment_status = 'paid'
        self.order.save()

        data = {
            "order_id": self.order.id,
            "token": "tok_visa"
        }
        response = self.client.post(self.payment_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Order not found or already paid.", str(response.data))

if __name__ == "__main__":
    import unittest
    unittest.main()