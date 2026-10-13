from django.shortcuts import render, redirect, get_object_or_404
from .models import Customer, Service, Order
from .forms import CustomerForm, ServiceForm, OrderForm, WeightRecordingForm, OrderPricingForm

def home(request):
    return render(request, 'home.html')

def customer_list(request):
    customers = Customer.objects.all().order_by('-date_registered')
    return render(request, 'customers/customer_list.html', {'customers': customers})

def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('customer_list')
    return render(request, 'customers/customer_form.html', {'form': form})

def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    return render(request, 'customers/customer_detail.html', {'customer': customer})

def service_list(request):
    services = Service.objects.all()
    return render(request, 'services/service_list.html', {'services': services})

def service_create(request):
    form = ServiceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('service_list')
    return render(request, 'services/service_form.html', {'form': form})

def service_update(request, pk):
    service = get_object_or_404(Service, pk=pk)
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('service_list')
    return render(request, 'services/service_form.html', {'form': form})

def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        service.delete()
        return redirect('service_list')
    return render(request, 'services/service_confirm_delete.html', {'service': service})

def order_list(request):
    orders = Order.objects.all().order_by('-date_received')
    return render(request, 'orders/order_list.html', {'orders': orders})

def order_create(request):
    form = OrderForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('order_list')
    return render(request, 'orders/order_form.html', {'form': form})

def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    return render(request, 'orders/order_detail.html', {'order': order})

def record_weight(request, pk):
    order = get_object_or_404(Order, pk=pk)
    form = WeightRecordingForm(request.POST or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('order_detail', pk=order.pk)
    return render(request, 'orders/record_weight.html', {'form': form, 'order': order})

def update_pricing_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    form = OrderPricingForm(request.POST or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('order_detail', pk=order.pk)
    return render(request, 'orders/update_pricing.html', {'form': form, 'order': order})