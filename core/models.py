import uuid
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone

class Course(models.Model):
    """Lookup table for the Course Management module (id, course_name)."""
    course_name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['course_name']

    def __str__(self):
        return self.course_name

class Customer(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    # New field: the selected course is stored as a foreign key (column course_id)
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers',
    )
    address = models.TextField(blank=True, null=True)
    date_registered = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.phone})"

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
    # Task 5 / Lab 16: Complete status tracking pipeline
    STATUS_CHOICES = [
        ('RECEIVED', 'Received'),
        ('WEIGHED', 'Weighed'),
        ('PRICED', 'Priced'),
        ('CONFIRMED', 'Confirmed'),
        ('WASHING', 'Washing'),
        ('DRYING', 'Drying'),
        ('FOLDING', 'Folding'),
        ('READY_FOR_RELEASE', 'Ready for Release'),
        ('RELEASED', 'Released'),
        ('CANCELLED', 'Cancelled'),
    ]

    order_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    
    # Task 4 / Lab 11: Weight measurement
    weight_kg = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(0.00)]
    )
    
    # Task 5 / Lab 15: Charges and discounts
    additional_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RECEIVED')
    is_paid = models.BooleanField(default=False)
    
    date_received = models.DateTimeField(default=timezone.now)
    expected_release_date = models.DateTimeField(blank=True, null=True)
    special_instructions = models.TextField(blank=True, null=True)

    def calculate_total(self):
        """Calculates total price = (weight * rate) + charges - discounts."""
        rate = self.service.price_per_kg if self.service else 0
        subtotal = (self.weight_kg * rate) + self.additional_charge
        self.total_price = max(0, subtotal - self.discount_amount)
        return self.total_price

    def save(self, *args, **kwargs):
        # Task 4 / Lab 9: Auto unique order number generation (e.g., ORD-20261013-A1B2)
        if not self.order_number:
            date_str = timezone.now().strftime("%Y%m%d")
            unique_id = str(uuid.uuid4().hex[:4]).upper()
            self.order_number = f"ORD-{date_str}-{unique_id}"
        
        # Task 5 / Lab 14: Automatic price calculation on save
        self.calculate_total()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.order_number} - {self.customer.name}"