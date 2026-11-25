import uuid
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

TWO_PLACES = Decimal('0.01')


def to_decimal(value):
    """Safely turn floats, ints, strings and None into a Decimal."""
    if value is None or value == '':
        return Decimal('0')
    return Decimal(str(value))


class Customer(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
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
    # Lab 18: estimated processing time, used to calculate the expected release date
    processing_hours = models.PositiveIntegerField(
        default=24,
        validators=[MinValueValidator(1)],
        help_text="Estimated processing time in hours. Used to calculate the expected release date.",
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
    FINAL_STATUSES = ('RELEASED', 'CANCELLED')
    PROCESSING_STATUSES = ('WASHING', 'DRYING', 'FOLDING')

    # Lab 17: the next step staff can take from each status (status -> (new status, button label))
    PROCESS_ACTIONS = {
        'PRICED': ('CONFIRMED', 'Confirm order'),
        'CONFIRMED': ('WASHING', 'Start washing'),
        'WASHING': ('DRYING', 'Complete washing and start drying'),
        'DRYING': ('FOLDING', 'Complete drying and start folding'),
        'FOLDING': ('READY_FOR_RELEASE', 'Complete folding, quality check passed: mark ready for release'),
    }

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
    expected_release_date = models.DateTimeField(
        blank=True, null=True,
        help_text="Leave blank to calculate it from the service's processing time.",
    )
    ready_at = models.DateTimeField(blank=True, null=True, editable=False)
    special_instructions = models.TextField(blank=True, null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loaded_status = self.status  # used to log status changes

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self._loaded_status = self.status

    # ---------- pricing ----------
    def calculate_total(self):
        """Total = (weight x rate) + additional charge - discount, never below zero.

        Values are converted to Decimal first, because a new Order starts with
        float defaults (0.0) and Python cannot multiply a float by a Decimal.
        """
        weight = to_decimal(self.weight_kg)
        charge = to_decimal(self.additional_charge)
        discount = to_decimal(self.discount_amount)
        rate = to_decimal(self.service.price_per_kg) if self.service_id else Decimal('0')

        subtotal = (weight * rate) + charge
        total = max(Decimal('0'), subtotal - discount)
        self.total_price = total.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        return self.total_price

    # ---------- payments ----------
    @property
    def paid_total(self):
        """Money received so far (change is not counted)."""
        if not self.pk:
            return Decimal('0.00')
        total = Decimal('0.00')
        for payment in self.payments.all():
            total += to_decimal(payment.amount_applied)
        return total

    @property
    def balance_due(self):
        balance = to_decimal(self.total_price) - self.paid_total
        return max(Decimal('0.00'), balance).quantize(TWO_PLACES)

    @property
    def is_fully_paid(self):
        total = to_decimal(self.total_price)
        return total > 0 and self.paid_total >= total

    @property
    def payment_label(self):
        total = to_decimal(self.total_price)
        if total <= 0:
            return 'Not billed'
        paid = self.paid_total
        if paid >= total:
            return 'Paid'
        if paid > 0:
            return 'Partial'
        return 'Unpaid'

    def payment_block_reason(self):
        """Why a payment cannot be taken right now ('' when it can)."""
        if self.status == 'CANCELLED':
            return 'This order was cancelled, so it cannot be paid.'
        if to_decimal(self.total_price) <= 0:
            return 'There is nothing to pay yet. Record the weight first so the price can be calculated.'
        if self.balance_due <= 0:
            return 'This order is already fully paid.'
        return ''

    def sync_paid_flag(self):
        """Keep the is_paid column in step with the payments."""
        flag = self.is_fully_paid
        if flag != self.is_paid:
            self.is_paid = flag
            Order.objects.filter(pk=self.pk).update(is_paid=flag)

    # ---------- processing ----------
    @property
    def has_weight(self):
        return to_decimal(self.weight_kg) > 0

    @property
    def is_closed(self):
        return self.status in self.FINAL_STATUSES

    @property
    def is_overdue(self):
        """Not finished and past the expected release date (Lab 18)."""
        return (
            not self.is_closed
            and self.expected_release_date is not None
            and self.expected_release_date <= timezone.now()
        )

    def next_action(self):
        """Returns (new_status, button label) for the next processing step, or None."""
        if self.is_closed:
            return None
        if self.status in ('RECEIVED', 'WEIGHED'):
            if self.has_weight:
                return ('PRICED', 'Mark as priced')
            return None
        return self.PROCESS_ACTIONS.get(self.status)

    def set_status(self, new_status):
        """Change the status; save() writes the history entry."""
        if new_status != self.status:
            self.status = new_status
            self.save()

    def save(self, *args, **kwargs):
        # Task 4 / Lab 9: Auto unique order number generation (e.g., ORD-20261013-A1B2)
        if not self.order_number:
            date_str = timezone.now().strftime("%Y%m%d")
            unique_id = str(uuid.uuid4().hex[:4]).upper()
            self.order_number = f"ORD-{date_str}-{unique_id}"

        is_new = self.pk is None

        # Lab 18: Order date + processing time = expected release date
        if not self.expected_release_date and self.service_id:
            base = self.date_received or timezone.now()
            self.expected_release_date = base + timedelta(hours=self.service.processing_hours)

        # Task 5 / Lab 14: Automatic price calculation on save
        self.calculate_total()

        if not is_new:
            self.is_paid = self.is_fully_paid

        if self.status == 'READY_FOR_RELEASE' and not self.ready_at:
            self.ready_at = timezone.now()

        previous_status = self._loaded_status
        super().save(*args, **kwargs)

        if is_new:
            StatusLog.objects.create(order=self, from_status='', to_status=self.status)
        elif previous_status != self.status:
            StatusLog.objects.create(order=self, from_status=previous_status, to_status=self.status)
        self._loaded_status = self.status

    def __str__(self):
        return f"Order #{self.order_number} - {self.customer.name}"


class StatusLog(models.Model):
    """History of every status change (processing time tracking)."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_logs')
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['changed_at', 'id']

    @property
    def to_label(self):
        return dict(Order.STATUS_CHOICES).get(self.to_status, self.to_status)

    def __str__(self):
        return f"{self.order.order_number}: {self.from_status or 'new'} -> {self.to_status}"


class Payment(models.Model):
    """Lab 19-22: a payment received for an order."""
    METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('DEBIT', 'Debit Card'),
        ('CREDIT', 'Credit Card'),
        ('EWALLET', 'E-wallet'),
    ]
    STATUS_CHOICES = [
        ('PARTIAL', 'Partial'),
        ('PAID', 'Paid'),
    ]

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payments')
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)  # balance before this payment
    amount_paid = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )  # money handed over by the customer
    amount_applied = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), editable=False)
    change = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), editable=False)
    payment_method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    reference_no = models.CharField(max_length=60, blank=True)
    payment_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PAID', editable=False)

    class Meta:
        ordering = ['payment_date', 'id']

    @property
    def receipt_number(self):
        return f"RCP-{self.pk:06d}" if self.pk else ''

    def save(self, *args, **kwargs):
        paid = to_decimal(self.amount_paid)
        due = to_decimal(self.amount_due)
        applied = min(paid, due)
        self.amount_applied = applied.quantize(TWO_PLACES)
        self.change = (paid - applied).quantize(TWO_PLACES)  # Lab 21: change is automatic
        self.status = 'PAID' if applied >= due else 'PARTIAL'
        super().save(*args, **kwargs)
        self.order.sync_paid_flag()

    def __str__(self):
        return f"{self.receipt_number} for {self.order.order_number}"


class Release(models.Model):
    """Lab 23-25: the record of laundry handed over to the customer."""
    release_number = models.CharField(max_length=20, unique=True, editable=False)
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name='release')
    released_at = models.DateTimeField(default=timezone.now)
    released_by = models.CharField(max_length=100)
    received_by = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-released_at']

    def save(self, *args, **kwargs):
        if not self.release_number:
            date_str = timezone.now().strftime("%Y%m%d")
            unique_id = str(uuid.uuid4().hex[:4]).upper()
            self.release_number = f"REL-{date_str}-{unique_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.release_number} ({self.order.order_number})"
