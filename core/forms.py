from django import forms
from .models import Customer, Service

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = '__all__'

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = '__all__'