from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Customer, Service, Order, Payment, Release


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = '__all__'


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = '__all__'


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['customer', 'service', 'expected_release_date', 'special_instructions']
        widgets = {
            # format makes the saved date show up correctly when editing an order
            'expected_release_date': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'type': 'datetime-local', 'class': 'form-control'},
            ),
            'special_instructions': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class WeightRecordingForm(forms.ModelForm):
    """Task 4: Laundry Weight Recording & Validation."""
    class Meta:
        model = Order
        fields = ['weight_kg']

    def clean_weight_kg(self):
        weight = self.cleaned_data.get('weight_kg')
        if weight is None or weight <= 0:
            raise forms.ValidationError("Weight must be greater than 0 kg.")
        return weight


class OrderPricingForm(forms.ModelForm):
    """Task 5: Additional Charges, Discounts & Status updating."""
    class Meta:
        model = Order
        fields = ['additional_charge', 'discount_amount', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Release and cancellation have their own actions with their own checks.
        blocked = set(Order.FINAL_STATUSES)
        self.fields['status'].choices = [c for c in Order.STATUS_CHOICES if c[0] not in blocked]
        self.fields['status'].help_text = (
            'Normally use the Next step button on the order page. '
            'Releasing and cancelling are separate actions.'
        )

    def clean_additional_charge(self):
        value = self.cleaned_data.get('additional_charge')
        if value is not None and value < 0:
            raise forms.ValidationError("The additional charge cannot be negative.")
        return value

    def clean_discount_amount(self):
        value = self.cleaned_data.get('discount_amount')
        if value is not None and value < 0:
            raise forms.ValidationError("The discount cannot be negative.")
        return value


class PaymentForm(forms.ModelForm):
    """Lab 20-21: record a payment and prevent invalid transactions."""

    class Meta:
        model = Payment
        fields = ['payment_method', 'amount_paid', 'reference_no']
        labels = {
            'payment_method': 'Payment method',
            'amount_paid': 'Amount received (₱)',
            'reference_no': 'Reference number',
        }
        help_texts = {
            'reference_no': 'Required for debit card, credit card and e-wallet payments.',
        }
        widgets = {
            'amount_paid': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
        }

    def __init__(self, *args, order=None, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        order = self.order

        reason = order.payment_block_reason()
        if reason:
            raise forms.ValidationError(reason)

        method = cleaned.get('payment_method')
        amount = cleaned.get('amount_paid')
        reference = (cleaned.get('reference_no') or '').strip()
        balance = order.balance_due

        if amount is not None and method:
            if method != 'CASH':
                if amount > balance:
                    self.add_error(
                        'amount_paid',
                        f"Card and e-wallet payments cannot be more than the balance (₱{balance}).",
                    )
                if not reference:
                    self.add_error('reference_no', 'Enter the reference number for this payment.')

            # Lab 21: a payment cannot be duplicated (for example a double click on Save)
            recent = timezone.now() - timedelta(seconds=60)
            if order.payments.filter(
                payment_method=method, amount_paid=amount, payment_date__gte=recent,
            ).exists():
                raise forms.ValidationError(
                    "This looks like a duplicate of a payment that was just recorded. "
                    "Check the payment list on the order before trying again."
                )
        return cleaned


class ReleaseForm(forms.ModelForm):
    """Lab 23-25: release laundry only when every rule is met."""

    order_number = forms.CharField(
        label='Confirm order number',
        help_text='Type the order number from the laundry tag or the bill.',
    )
    customer_verified = forms.BooleanField(
        label="I have checked the customer's identity",
        error_messages={'required': 'Please confirm that the customer has been verified.'},
    )

    class Meta:
        model = Release
        fields = ['released_by', 'received_by', 'notes']
        labels = {
            'released_by': 'Released by (staff name)',
            'received_by': 'Received by (customer or representative)',
            'notes': 'Notes',
        }
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, order=None, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)
        self.order_fields(['order_number', 'customer_verified', 'released_by', 'received_by', 'notes'])

    def clean(self):
        cleaned = super().clean()
        order = self.order
        problems = []

        if order.status == 'RELEASED' or Release.objects.filter(order=order).exists():
            problems.append('This order has already been released.')
        elif order.status == 'CANCELLED':
            problems.append('This order was cancelled and cannot be released.')
        else:
            if order.status != 'READY_FOR_RELEASE':
                problems.append(
                    f'The laundry is not finished yet. Its status is "{order.get_status_display()}", '
                    'and it must be "Ready for Release".'
                )
            if not order.is_fully_paid:
                problems.append(f'Payment is not complete. Outstanding balance: ₱{order.balance_due}.')

        if problems:
            raise forms.ValidationError(problems)

        typed = (cleaned.get('order_number') or '').strip().upper()
        if typed and typed != order.order_number.upper():
            self.add_error('order_number', 'This does not match the order number of this order.')
        return cleaned
