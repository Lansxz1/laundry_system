from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import reports
from .forms import (
    CustomerForm, ServiceForm, OrderForm, WeightRecordingForm, OrderPricingForm,
    PaymentForm, ReleaseForm,
)
from .models import Customer, Service, Order, Payment, Release


def home(request):
    return render(request, 'home.html')


def dashboard(request):
    return render(request, 'dashboard.html', {'data': reports.dashboard_data()})


# ---------- Customers ----------

def customer_list(request):
    customers = Customer.objects.all().order_by('-date_registered')
    return render(request, 'customers/customer_list.html', {'customers': customers})


def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Customer added.')
        return redirect('customer_list')
    return render(request, 'customers/customer_form.html', {'form': form})


def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    orders = customer.orders.select_related('service').prefetch_related('payments').order_by('-date_received')
    return render(request, 'customers/customer_detail.html', {'customer': customer, 'orders': orders})


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
    payment_count = Payment.objects.filter(order__customer=customer).count()
    blocked = payment_count > 0  # payments are financial records and must be kept
    if request.method == 'POST' and not blocked:
        customer.delete()
        messages.success(request, 'Customer deleted.')
        return redirect('customer_list')
    return render(request, 'customers/customer_confirm_delete.html', {
        'customer': customer,
        'order_count': customer.orders.count(),
        'payment_count': payment_count,
        'blocked': blocked,
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

def _closed_guard(request, order):
    """Closed orders (released or cancelled) can no longer be changed."""
    if order.is_closed:
        messages.error(
            request,
            f'This order is {order.get_status_display().lower()}, so it can no longer be changed.',
        )
        return redirect('order_detail', pk=order.pk)
    return None


def order_list(request):
    orders = list(
        Order.objects.select_related('customer', 'service')
        .prefetch_related('payments').order_by('-date_received')
    )
    active = request.GET.get('filter', '')
    if active == 'ready':
        orders = [o for o in orders if o.status == 'READY_FOR_RELEASE']
    elif active == 'due':
        orders = [o for o in orders if o.is_overdue]
    elif active == 'unpaid':
        orders = [o for o in orders if o.status != 'CANCELLED' and o.payment_label in ('Unpaid', 'Partial')]
    else:
        active = ''
    return render(request, 'orders/order_list.html', {'orders': orders, 'active_filter': active})


def order_create(request):
    form = OrderForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        order = form.save()
        messages.success(request, f'Order {order.order_number} created. Record the weight next.')
        return redirect('order_detail', pk=order.pk)
    return render(request, 'orders/order_form.html', {'form': form})


def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related('customer', 'service'), pk=pk)
    release = Release.objects.filter(order=order).first()
    return render(request, 'orders/order_detail.html', {
        'order': order,
        'payments': order.payments.all(),
        'release': release,
        'logs': order.status_logs.all(),
        'next_action': order.next_action(),
        'can_pay': not order.payment_block_reason(),
        'balance': order.balance_due,
        'paid': order.paid_total,
    })


def order_update(request, pk):
    order = get_object_or_404(Order, pk=pk)
    guard = _closed_guard(request, order)
    if guard:
        return guard
    form = OrderForm(request.POST or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Order updated.')
        return redirect('order_detail', pk=order.pk)
    return render(request, 'orders/order_form.html', {'form': form, 'order': order})


def order_delete(request, pk):
    order = get_object_or_404(Order, pk=pk)
    payment_count = order.payments.count()
    released = Release.objects.filter(order=order).exists()
    blocked = payment_count > 0 or released
    if request.method == 'POST' and not blocked:
        order.delete()
        messages.success(request, 'Order deleted.')
        return redirect('order_list')
    return render(request, 'orders/order_confirm_delete.html', {
        'order': order,
        'payment_count': payment_count,
        'blocked': blocked,
    })


def record_weight(request, pk):
    order = get_object_or_404(Order, pk=pk)
    guard = _closed_guard(request, order)
    if guard:
        return guard
    form = WeightRecordingForm(request.POST or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if order.status in ('RECEIVED', 'WEIGHED'):
            order.set_status('PRICED')  # Lab 37: the status moves on by itself
            messages.success(request, 'Weight saved and the price calculated. The order is now Priced.')
        else:
            messages.success(request, 'Weight saved and the price recalculated.')
        return redirect('order_detail', pk=order.pk)
    return render(request, 'orders/record_weight.html', {'form': form, 'order': order})


def update_pricing_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    guard = _closed_guard(request, order)
    if guard:
        return guard
    form = OrderPricingForm(request.POST or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Order updated.')
        return redirect('order_detail', pk=order.pk)
    return render(request, 'orders/update_pricing.html', {'form': form, 'order': order})


@require_POST
def order_advance(request, pk):
    """Lab 17: move the order to its next processing step."""
    order = get_object_or_404(Order, pk=pk)
    action = order.next_action()
    if order.is_closed:
        messages.error(request, 'This order is closed and cannot move forward.')
    elif action is None:
        messages.error(request, 'Record the weight first. The order cannot move forward without it.')
    else:
        order.set_status(action[0])
        messages.success(request, f'Order moved to {order.get_status_display()}.')
    return redirect('order_detail', pk=order.pk)


def order_cancel(request, pk):
    order = get_object_or_404(Order, pk=pk)
    reason = ''
    if order.is_closed:
        reason = f'This order is already {order.get_status_display().lower()}.'
    elif order.payments.exists():
        reason = 'This order already has payments, so it cannot be cancelled.'
    if request.method == 'POST' and not reason:
        order.set_status('CANCELLED')
        messages.success(request, 'Order cancelled.')
        return redirect('order_detail', pk=order.pk)
    return render(request, 'orders/order_cancel_confirm.html', {'order': order, 'reason': reason})


def order_bill(request, pk):
    """Lab 19: the customer's bill."""
    order = get_object_or_404(Order.objects.select_related('customer', 'service'), pk=pk)
    return render(request, 'orders/order_bill.html', {
        'order': order,
        'subtotal': order.weight_kg * order.service.price_per_kg,
        'paid': order.paid_total,
        'balance': order.balance_due,
        'today': timezone.localdate(),
    })


# ---------- Payments ----------

def payment_create(request, pk):
    order = get_object_or_404(Order.objects.select_related('customer', 'service'), pk=pk)
    form = PaymentForm(request.POST or None, order=order)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            payment = form.save(commit=False)
            payment.order = order
            payment.amount_due = order.balance_due
            payment.save()
        messages.success(request, 'Payment recorded.')
        return redirect('payment_receipt', pk=payment.pk)
    return render(request, 'payments/payment_form.html', {
        'order': order,
        'form': form,
        'reason': order.payment_block_reason(),
        'paid': order.paid_total,
        'balance': order.balance_due,
    })


def payment_receipt(request, pk):
    """Lab 22: printable receipt."""
    payment = get_object_or_404(Payment.objects.select_related('order__customer', 'order__service'), pk=pk)
    order = payment.order
    return render(request, 'payments/receipt.html', {
        'payment': payment,
        'order': order,
        'subtotal': order.weight_kg * order.service.price_per_kg,
        'balance': order.balance_due,
    })


# ---------- Release ----------

def release_create(request, pk):
    order = get_object_or_404(Order.objects.select_related('customer', 'service'), pk=pk)
    form = ReleaseForm(request.POST or None, order=order)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            release = form.save(commit=False)
            release.order = order
            release.released_at = timezone.now()
            release.save()
            order.set_status('RELEASED')
        messages.success(request, f'Laundry released. Release number {release.release_number}.')
        return redirect('release_detail', pk=release.pk)
    checks = [
        ('The laundry is ready for release', order.status == 'READY_FOR_RELEASE'),
        ('Payment is complete', order.is_fully_paid),
        ('The order is still open', not order.is_closed),
    ]
    return render(request, 'releases/release_form.html', {
        'order': order,
        'form': form,
        'checks': checks,
        'balance': order.balance_due,
    })


def release_detail(request, pk):
    release = get_object_or_404(Release.objects.select_related('order__customer', 'order__service'), pk=pk)
    return render(request, 'releases/release_detail.html', {'release': release, 'order': release.order})


# ---------- Reports ----------

def reports_home(request):
    return render(request, 'reports/reports_home.html')


def report_daily(request):
    today = timezone.localdate()
    day = reports.parse_date(request.GET.get('date'), today)
    status = request.GET.get('status', '')
    data = reports.daily_orders_report(day, status)
    return render(request, 'reports/daily.html', {
        'day': day, 'status': status, 'statuses': Order.STATUS_CHOICES, **data,
    })


def report_processing(request):
    status = request.GET.get('status', '')
    data = reports.processing_report(status)
    return render(request, 'reports/processing.html', {'status': status, **data})


def report_revenue(request):
    start, end = reports.get_range(request)
    data = reports.revenue_report(start, end)
    return render(request, 'reports/revenue.html', {'start': start, 'end': end, **data})


def report_customers(request):
    start, end = reports.get_range(request)
    data = reports.customer_report(start, end)
    return render(request, 'reports/customers.html', {'start': start, 'end': end, **data})


def report_services(request):
    start, end = reports.get_range(request)
    data = reports.service_report(start, end)
    return render(request, 'reports/services.html', {'start': start, 'end': end, **data})
