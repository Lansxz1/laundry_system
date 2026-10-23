from django.contrib import messages
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from .models import Course, Customer, Service, Order
from .forms import CourseForm, CustomerForm, ServiceForm, OrderForm, WeightRecordingForm, OrderPricingForm


def home(request):
    return render(request, 'home.html')


# ---------- Courses ----------

def course_list(request):
    courses = Course.objects.annotate(customer_count=Count('customers'))
    return render(request, 'courses/course_list.html', {'courses': courses})


def course_create(request):
    form = CourseForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Course added.')
        return redirect('course_list')
    return render(request, 'courses/course_form.html', {'form': form})


def course_update(request, pk):
    course = get_object_or_404(Course, pk=pk)
    form = CourseForm(request.POST or None, instance=course)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Course updated.')
        return redirect('course_list')
    return render(request, 'courses/course_form.html', {'form': form})


def course_delete(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == 'POST':
        course.delete()
        messages.success(request, 'Course deleted.')
        return redirect('course_list')
    return render(request, 'courses/course_confirm_delete.html', {
        'course': course,
        'customer_count': course.customers.count(),
    })


# ---------- Customers ----------

def customer_list(request):
    customers = Customer.objects.select_related('course').order_by('-date_registered')
    return render(request, 'customers/customer_list.html', {'customers': customers})


def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Customer added.')
        return redirect('customer_list')
    return render(request, 'customers/customer_form.html', {'form': form})


def customer_detail(request, pk):
    customer = get_object_or_404(Customer.objects.select_related('course'), pk=pk)
    return render(request, 'customers/customer_detail.html', {'customer': customer})


def customer_update(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Customer updated.')
        return redirect('customer_detail', pk=customer.pk)
    return render(request, 'customers/customer_form.html', {'form': form})


def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer.delete()
        messages.success(request, 'Customer deleted.')
        return redirect('customer_list')
    return render(request, 'customers/customer_confirm_delete.html', {
        'customer': customer,
        'order_count': customer.orders.count(),
    })


# ---------- Services ----------

def service_list(request):
    services = Service.objects.all()
    return render(request, 'services/service_list.html', {'services': services})


def service_create(request):
    form = ServiceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Service added.')
        return redirect('service_list')
    return render(request, 'services/service_form.html', {'form': form})


def service_update(request, pk):
    service = get_object_or_404(Service, pk=pk)
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Service updated.')
        return redirect('service_list')
    return render(request, 'services/service_form.html', {'form': form})


def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk)
    order_count = service.order_set.count()
    if request.method == 'POST' and order_count == 0:
        service.delete()
        messages.success(request, 'Service deleted.')
        return redirect('service_list')
    return render(request, 'services/service_confirm_delete.html', {
        'service': service,
        'order_count': order_count,
        'blocked': order_count > 0,
    })


# ---------- Orders ----------

def order_list(request):
    orders = Order.objects.all().order_by('-date_received')
    return render(request, 'orders/order_list.html', {'orders': orders})


def order_create(request):
    form = OrderForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Order created.')
        return redirect('order_list')
    return render(request, 'orders/order_form.html', {'form': form})


def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    return render(request, 'orders/order_detail.html', {'order': order})


def order_update(request, pk):
    order = get_object_or_404(Order, pk=pk)
    form = OrderForm(request.POST or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Order updated.')
        return redirect('order_detail', pk=order.pk)
    return render(request, 'orders/order_form.html', {'form': form, 'order': order})


def order_delete(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        order.delete()
        messages.success(request, 'Order deleted.')
        return redirect('order_list')
    return render(request, 'orders/order_confirm_delete.html', {'order': order})


def record_weight(request, pk):
    order = get_object_or_404(Order, pk=pk)
    form = WeightRecordingForm(request.POST or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Weight saved.')
        return redirect('order_detail', pk=order.pk)
    return render(request, 'orders/record_weight.html', {'form': form, 'order': order})


def update_pricing_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    form = OrderPricingForm(request.POST or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Order updated.')
        return redirect('order_detail', pk=order.pk)
    return render(request, 'orders/update_pricing.html', {'form': form, 'order': order})