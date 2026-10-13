from django.shortcuts import render, redirect, get_object_or_404
from .models import Customer, Service, Order
from .forms import CustomerForm, ServiceForm, OrderForm, WeightRecordingForm, OrderPricingForm

# --- HOME VIEW ---

def home(request):
    return render(request, 'home.html')


# --- CUSTOMER VIEWS ---

def customer_list(request):
    customers = Customer.objects.all().order_by('-created_at')
    return render(request, 'customers/customer_list.html', {'customers': customers})

def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('customer_list')
    else:
        form = CustomerForm()
    return render(request, 'customers/customer_form.html', {'form': form, 'title': 'Register Customer'})

def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    orders = customer.orders.all().order_by('-created_at')
    return render(request, 'customers/customer_detail.html', {'customer': customer, 'orders': orders})


# --- SERVICE VIEWS ---

def service_list(request):
    services = Service.objects.all()
    return render(request, 'services/service_list.html', {'services': services})

def service_create(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('service_list')
    else:
        form = ServiceForm()
    return render(request, 'services/service_form.html', {'form': form, 'title': 'Add Service'})

def service_update(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            return redirect('service_list')
    else:
        form = ServiceForm(instance=service)
    return render(request, 'services/service_form.html', {'form': form, 'title': 'Edit Service'})

def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        service.delete()
        return redirect('service_list')
    return render(request, 'services/service_confirm_delete.html', {'service': service})

# ORDER VIEWS (Task 4 & Task 5)
def order_list(request):
    orders = Order.objects.all().order_by('-date_received')
    return render(request, 'orders/order_list.html', {'orders': orders})

def order_create(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save()
            return redirect('order_detail', pk=order.pk)
    else:
        form = OrderForm()
    return render(request, 'orders/order_form.html', {'form': form, 'title': 'Create Laundry Order'})

def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    return render(request, 'orders/order_detail.html', {'order': order})

def record_weight(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        form = WeightRecordingForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save(commit=False)
            if order.status == 'RECEIVED':
                order.status = 'WEIGHED'
            order.save()
            return redirect('order_detail', pk=order.pk)
    else:
        form = WeightRecordingForm(instance=order)
    return render(request, 'orders/record_weight.html', {'form': form, 'order': order})

def update_pricing_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        form = OrderPricingForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            return redirect('order_detail', pk=order.pk)
    else:
        form = OrderPricingForm(instance=order)
    return render(request, 'orders/update_pricing.html', {'form': form, 'order': order})