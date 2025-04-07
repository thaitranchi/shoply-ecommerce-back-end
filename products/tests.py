from django.test import TestCase
from .models import Product

class ProductModelTest(TestCase):

    # ✅ Setup method to create sample products before each test
    def setUp(self):
        self.product = Product.objects.create(
            name="Gaming Laptop",
            description="A high-end gaming laptop",
            price=1500.99,
            stock=10
        )

    # ✅ Test string representation
    def test_product_str(self):
        self.assertEqual(str(self.product), "Gaming Laptop")

    # ✅ Test product creation
    def test_create_product(self):
        product_count = Product.objects.count()
        self.assertEqual(product_count, 1)
        self.assertEqual(self.product.name, "Gaming Laptop")
        self.assertEqual(float(self.product.price), 1500.99)
        self.assertEqual(self.product.stock, 10)

    # ✅ Test updating a product
    def test_update_product(self):
        self.product.name = "Gaming Laptop Pro"
        self.product.price = 1700.99
        self.product.save()

        updated_product = Product.objects.get(id=self.product.id)
        self.assertEqual(updated_product.name, "Gaming Laptop Pro")
        self.assertEqual(float(updated_product.price), 1700.99)

    # ✅ Test deleting a product
    def test_delete_product(self):
        self.product.delete()
        product_count = Product.objects.count()
        self.assertEqual(product_count, 0)

    # ✅ Test default stock value
    def test_default_stock(self):
        product = Product.objects.create(
            name="Wireless Mouse",
            description="A reliable wireless mouse",
            price=29.99
        )
        self.assertEqual(product.stock, 0)
