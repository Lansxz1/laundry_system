"""Report and dashboard calculations (Lab 26-31)."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import Customer, Order, Payment, Service, to_decimal

ZERO = Decimal('0.00')


# ---------- small helpers ----------

def parse_date(value, default):
    """Read a YYYY-MM-DD text; fall back to the default when it is empty or wrong."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return default


def month_bounds(day):
    start = day.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    return start, next_month - timedelta(days=1)


def week_bounds(day):
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def get_range(request):
    """Start and end dates from ?start=&end= (default: this month so far)."""
    today = timezone.localdate()
    start = parse_date(request.GET.get('start'), today.replace(day=1))
    end = parse_date(request.GET.get('end'), today)
    if start > end:
        start, end = end, start
    return start, end


def revenue_between(start, end):
    """Money received between two dates (change given back is not counted)."""
    total = Payment.objects.filter(
        payment_date__date__gte=start, payment_date__date__lte=end,
    ).aggregate(total=Sum('amount_applied'))['total']
    return total or ZERO


def order_money(orders):
    """Count, weight and billed amount of a list of orders."""
    weight = ZERO
    amount = ZERO
    for order in orders:
        weight += to_decimal(order.weight_kg)
        amount += to_decimal(order.total_price)
    return {'count': len(orders), 'weight': weight, 'amount': amount}


def unpaid_orders():
    """Orders that are billed but not fully paid (excluding cancelled ones)."""
    orders = (
        Order.objects.exclude(status='CANCELLED')
        .filter(total_price__gt=0)
        .select_related('customer', 'service')
        .prefetch_related('payments')
        .order_by('date_received')
    )
    return [o for o in orders if not o.is_fully_paid]


# ---------- dashboard (Lab 31) ----------

def dashboard_data():
    today = timezone.localdate()
    week_start, week_end = week_bounds(today)
    month_start, month_end = month_bounds(today)

    unpaid = unpaid_orders()
    due = list(
        Order.objects.exclude(status__in=Order.FINAL_STATUSES)
        .filter(expected_release_date__lte=timezone.now())
        .select_related('customer', 'service')
        .order_by('expected_release_date')
    )
    counts = defaultdict(int)
    for service_id in Order.objects.exclude(status='CANCELLED').values_list('service_id', flat=True):
        counts[service_id] += 1
    services = {s.pk: s for s in Service.objects.filter(pk__in=counts.keys())}
    popular_rows = sorted(
        ({'service': services[sid], 'orders': n} for sid, n in counts.items() if sid in services),
        key=lambda row: -row['orders'],
    )[:5]
    top_orders = max((row['orders'] for row in popular_rows), default=0)
    for row in popular_rows:
        row['pct'] = int(row['orders'] / top_orders * 100) if top_orders else 0

    return {
        'today': today,
        'customers': Customer.objects.count(),
        'orders_today': Order.objects.filter(date_received__date=today).count(),
        'revenue_today': revenue_between(today, today),
        'revenue_week': revenue_between(week_start, week_end),
        'revenue_month': revenue_between(month_start, month_end),
        'ready': Order.objects.filter(status='READY_FOR_RELEASE').count(),
        'processing': Order.objects.filter(status__in=Order.PROCESSING_STATUSES).count(),
        'unpaid_count': len(unpaid),
        'unpaid_total': sum((o.balance_due for o in unpaid), ZERO),
        'due_count': len(due),
        'due_orders': due[:5],
        'popular': popular_rows,
        'recent': Order.objects.select_related('customer', 'service').order_by('-date_received')[:5],
    }


# ---------- Lab 26: daily orders ----------

def daily_orders_report(day, status=''):
    orders = Order.objects.filter(date_received__date=day).select_related('customer', 'service').order_by('date_received')
    if status in dict(Order.STATUS_CHOICES):
        orders = orders.filter(status=status)
    orders = list(orders)
    return {'orders': orders, 'totals': order_money(orders)}


# ---------- Lab 27: processing ----------

def processing_report(status=''):
    counts = {code: 0 for code, _ in Order.STATUS_CHOICES}
    for order in Order.objects.all():
        counts[order.status] += 1
    rows = [{'code': code, 'label': label, 'count': counts[code]} for code, label in Order.STATUS_CHOICES]

    orders = Order.objects.select_related('customer', 'service').order_by('expected_release_date', 'date_received')
    if status in counts:
        orders = orders.filter(status=status)
    else:
        orders = orders.exclude(status__in=Order.FINAL_STATUSES)
    orders = list(orders)

    # average processing time = received until ready for release
    done = [o for o in Order.objects.filter(ready_at__isnull=False)]
    avg_hours = None
    if done:
        seconds = sum((o.ready_at - o.date_received).total_seconds() for o in done)
        avg_hours = round(seconds / len(done) / 3600, 1)

    return {'rows': rows, 'orders': orders, 'avg_hours': avg_hours, 'total': sum(counts.values())}


# ---------- Lab 28: payment and revenue ----------

def revenue_report(start, end):
    today = timezone.localdate()
    week_start, week_end = week_bounds(today)
    month_start, month_end = month_bounds(today)

    payments = list(
        Payment.objects.filter(payment_date__date__gte=start, payment_date__date__lte=end)
        .select_related('order__service', 'order__customer')
    )
    by_day = defaultdict(lambda: {'count': 0, 'total': ZERO})
    by_service = defaultdict(lambda: {'count': 0, 'total': ZERO})
    by_method = defaultdict(lambda: {'count': 0, 'total': ZERO})
    labels = dict(Payment.METHOD_CHOICES)
    total = ZERO
    for p in payments:
        day = timezone.localtime(p.payment_date).date()
        for bucket, key in ((by_day, day), (by_service, p.order.service.name), (by_method, labels.get(p.payment_method, p.payment_method))):
            bucket[key]['count'] += 1
            bucket[key]['total'] += p.amount_applied
        total += p.amount_applied

    def rows(bucket, sort_key):
        out = [{'name': k, 'count': v['count'], 'total': v['total']} for k, v in bucket.items()]
        out.sort(key=sort_key)
        top = max((r['total'] for r in out), default=ZERO)
        for r in out:
            r['pct'] = int(r['total'] / top * 100) if top else 0
        return out

    unpaid = unpaid_orders()
    return {
        'range_total': total,
        'payments_count': len(payments),
        'today': revenue_between(today, today),
        'week': revenue_between(week_start, week_end),
        'month': revenue_between(month_start, month_end),
        'week_range': (week_start, week_end),
        'month_range': (month_start, month_end),
        'daily': rows(by_day, lambda r: r['name']),
        'by_service': rows(by_service, lambda r: -r['total']),
        'by_method': rows(by_method, lambda r: -r['total']),
        'unpaid': unpaid,
        'unpaid_total': sum((o.balance_due for o in unpaid), ZERO),
    }


# ---------- Lab 29: customers ----------

def customer_report(start, end):
    orders = list(
        Order.objects.filter(date_received__date__gte=start, date_received__date__lte=end)
        .exclude(status='CANCELLED').select_related('customer')
    )
    earlier_ids = set(
        Order.objects.filter(date_received__date__lt=start)
        .exclude(status='CANCELLED').values_list('customer_id', flat=True)
    )

    stats = {}
    for o in orders:
        row = stats.setdefault(o.customer_id, {'customer': o.customer, 'orders': 0, 'spent': ZERO, 'returning': o.customer_id in earlier_ids})
        row['orders'] += 1
        row['spent'] += to_decimal(o.total_price)
    rows = sorted(stats.values(), key=lambda r: (-r['orders'], -r['spent']))

    return {
        'total_customers': Customer.objects.count(),
        'new_customers': Customer.objects.filter(
            date_registered__date__gte=start, date_registered__date__lte=end).count(),
        'active_customers': len(rows),
        'returning_customers': sum(1 for r in rows if r['returning']),
        'rows': rows,
        'spent_total': sum((r['spent'] for r in rows), ZERO),
    }


# ---------- Lab 30: service performance ----------

def service_report(start, end):
    orders = list(
        Order.objects.filter(date_received__date__gte=start, date_received__date__lte=end)
        .exclude(status='CANCELLED').select_related('service').prefetch_related('payments')
    )
    stats = {}
    for o in orders:
        row = stats.setdefault(o.service_id, {'service': o.service, 'orders': 0, 'weight': ZERO, 'billed': ZERO, 'revenue': ZERO})
        row['orders'] += 1
        row['weight'] += to_decimal(o.weight_kg)
        row['billed'] += to_decimal(o.total_price)
        row['revenue'] += o.paid_total
    rows = sorted(stats.values(), key=lambda r: (-r['orders'], -r['billed']))
    top = max((r['orders'] for r in rows), default=0)
    for r in rows:
        r['pct'] = int(r['orders'] / top * 100) if top else 0
    return {
        'rows': rows,
        'orders_total': sum(r['orders'] for r in rows),
        'weight_total': sum((r['weight'] for r in rows), ZERO),
        'billed_total': sum((r['billed'] for r in rows), ZERO),
        'revenue_total': sum((r['revenue'] for r in rows), ZERO),
    }
