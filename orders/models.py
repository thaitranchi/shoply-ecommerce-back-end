from django.conf import settings
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from products.models import Product

# orders/models.py
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    payment_status = models.CharField(max_length=20, default='unpaid')  # unpaid, paid, failed
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_refunded = models.BooleanField(default=False)
    refund_id = models.CharField(max_length=100, blank=True, null=True)

    def update_total_price(self):
        # Safely recalculate the total price
        self.total_price = sum(item.price * item.quantity for item in self.items.all())
        self.save(update_fields=['total_price'])
    
    def save(self, *args, **kwargs):
            """Track status changes automatically before saving."""
            if self.pk:
                old_order = Order.objects.get(pk=self.pk)
                if old_order.status != self.status:
                    OrderStatusHistory.objects.create(
                        order=self,
                        previous_status=old_order.status,
                        new_status=self.status
                    )

            super().save(*args, **kwargs)
            
    def __str__(self):
        return f"Order #{self.id} - {self.get_status_display()} by {self.user.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def clean(self):
        """Check stock availability before saving."""
        if self.quantity > self.product.stock:
            raise ValidationError(f"Insufficient stock for {self.product.name}. Available: {self.product.stock}")

    @transaction.atomic
    def save(self, *args, **kwargs):
        """Ensure stock update is atomic and prevent race conditions."""
        with transaction.atomic():
            product = Product.objects.select_for_update().get(id=self.product.id)

            if self.quantity > product.stock:
                raise ValidationError(f"Insufficient stock for {product.name}. Available: {product.stock}")

            # If price is not set, use product price
            if not self.price:
                self.price = product.price

            # Reduce stock
            product.stock -= self.quantity
            product.save()

            super().save(*args, **kwargs)

            # Update order total price
            self.order.update_total_price()

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    previous_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.order.id} changed from {self.previous_status} to {self.new_status} on {self.changed_at}"

@receiver(post_save, sender=OrderItem)
@receiver(post_delete, sender=OrderItem)
def update_order_total(sender, instance, **kwargs):
    order = instance.order
    order.total_price = sum(item.price * item.quantity for item in order.items.all())
    order.save()

@receiver(post_save, sender=Order)
def log_order_status_change(sender, instance, created, **kwargs):
    if not created:
        previous_status = instance.__class__.objects.get(pk=instance.pk).status
        if previous_status != instance.status:
            OrderStatusHistory.objects.create(
                order=instance,
                previous_status=previous_status,
                new_status=instance.status
            )