from django.db import models

# Create your models here.
from django.core.validators import MinValueValidator

class Customer(models.Model):
    name = models.CharField(max_length=100)  # Check what this field is actually named!
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Service(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price_per_kg = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        validators=[MinValueValidator(0.00)]
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - ₱{self.price_per_kg}/kg"

class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('DONE', 'Done'),
        ('RELEASED', 'Released'),
    ]

    order_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    weight_kg = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[MinValueValidator(0.10)]
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.service and self.weight_kg:
            self.total_price = self.service.price_per_kg * self.weight_kg
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.order_number} - {self.customer}"