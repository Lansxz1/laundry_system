from django import forms
from .models import Customer, Service, Order

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
            'expected_release_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
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
        