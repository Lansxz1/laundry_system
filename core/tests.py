from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Customer, Service, Order, Payment, Release


def make_order(weight='6.5', rate='50', hours=24):
    """A customer and an order with a weight, so the total is rate x weight."""
    customer = Customer.objects.create(name='Juan Dela Cruz', phone='09171234567')
    service, _ = Service.objects.get_or_create(
        name='Wash and Fold', defaults={'price_per_kg': Decimal(rate), 'processing_hours': hours},
    )
    return Order.objects.create(customer=customer, service=service, weight_kg=Decimal(weight))


def pay_in_full(order, amount=None):
    amount = Decimal(amount) if amount is not None else order.balance_due
    return Payment.objects.create(
        order=order, amount_due=order.balance_due, amount_paid=amount, payment_method='CASH',
    )


class CustomerTests(TestCase):
    """UT-01 to UT-03, UT-15."""

    def test_register_customer(self):
        response = self.client.post(reverse('customer_create'), {
            'name': 'Juan Dela Cruz', 'phone': '09171234567',
        })
        self.assertRedirects(response, reverse('customer_list'))
        self.assertTrue(Customer.objects.filter(name='Juan Dela Cruz').exists())

    def test_missing_phone_is_rejected(self):
        response = self.client.post(reverse('customer_create'), {'name': 'No Phone'})
        self.assertEqual(response.status_code, 200)  # form shown again with an error
        self.assertFalse(Customer.objects.filter(name='No Phone').exists())

    def test_edit_customer(self):
        customer = Customer.objects.create(name='Ana Cruz', phone='09170000000')
        response = self.client.post(reverse('customer_update', args=[customer.pk]), {
            'name': 'Ana Cruz', 'phone': '09179999999',
        })
        self.assertRedirects(response, reverse('customer_detail', args=[customer.pk]))
        customer.refresh_from_db()
        self.assertEqual(customer.phone, '09179999999')

    def test_delete_customer_also_deletes_orders(self):
        customer = Customer.objects.create(name='Ana Cruz', phone='09170000000')
        service = Service.objects.create(name='Wash and Fold', price_per_kg=Decimal('50'))
        Order.objects.create(customer=customer, service=service)
        response = self.client.post(reverse('customer_delete', args=[customer.pk]))
        self.assertRedirects(response, reverse('customer_list'))
        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(Order.objects.count(), 0)

    def test_customer_with_payments_cannot_be_deleted(self):
        order = make_order()
        pay_in_full(order)
        response = self.client.post(reverse('customer_delete', args=[order.customer.pk]))
        self.assertEqual(response.status_code, 200)  # explanation page
        self.assertTrue(Customer.objects.filter(pk=order.customer.pk).exists())


class ServiceTests(TestCase):
    """UT-04 to UT-07."""

    def test_add_service(self):
        response = self.client.post(reverse('service_create'), {
            'name': 'Wash and Fold', 'description': '', 'price_per_kg': '50',
            'processing_hours': '24', 'is_active': 'on',
        })
        self.assertRedirects(response, reverse('service_list'))
        self.assertTrue(Service.objects.filter(name='Wash and Fold').exists())

    def test_negative_rate_is_rejected(self):
        response = self.client.post(reverse('service_create'), {
            'name': 'Bad Rate', 'description': '', 'price_per_kg': '-10',
            'processing_hours': '24', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Service.objects.filter(name='Bad Rate').exists())

    def test_processing_time_must_be_at_least_one_hour(self):
        response = self.client.post(reverse('service_create'), {
            'name': 'Zero Hours', 'description': '', 'price_per_kg': '50',
            'processing_hours': '0', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Service.objects.filter(name='Zero Hours').exists())

    def test_duplicate_name_is_rejected(self):
        Service.objects.create(name='Wash and Fold', price_per_kg=Decimal('50'))
        response = self.client.post(reverse('service_create'), {
            'name': 'Wash and Fold', 'description': '', 'price_per_kg': '60',
            'processing_hours': '24', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Service.objects.filter(name='Wash and Fold').count(), 1)

    def test_service_in_use_cannot_be_deleted(self):
        customer = Customer.objects.create(name='Ana Cruz', phone='09170000000')
        service = Service.objects.create(name='Wash and Fold', price_per_kg=Decimal('50'))
        Order.objects.create(customer=customer, service=service)
        response = self.client.post(reverse('service_delete', args=[service.pk]))
        self.assertEqual(response.status_code, 200)  # explanation page, not a redirect
        self.assertTrue(Service.objects.filter(pk=service.pk).exists())

    def test_unused_service_can_be_deleted(self):
        service = Service.objects.create(name='Ironing', price_per_kg=Decimal('30'))
        response = self.client.post(reverse('service_delete', args=[service.pk]))
        self.assertRedirects(response, reverse('service_list'))
        self.assertFalse(Service.objects.filter(pk=service.pk).exists())


class OrderTests(TestCase):
    """UT-08 to UT-14 and the integration tests."""

    def setUp(self):
        self.customer = Customer.objects.create(name='Juan Dela Cruz', phone='09171234567')
        self.service = Service.objects.create(name='Wash and Fold', price_per_kg=Decimal('50'))

    def test_create_order_from_form(self):
        response = self.client.post(reverse('order_create'), {
            'customer': self.customer.pk, 'service': self.service.pk,
            'expected_release_date': '', 'special_instructions': '',
        })
        order = Order.objects.get()
        self.assertRedirects(response, reverse('order_detail', args=[order.pk]))

    def test_order_number_format(self):
        order = Order.objects.create(customer=self.customer, service=self.service)
        self.assertRegex(order.order_number, r'^ORD-\d{8}-[0-9A-F]{4}$')

    def test_order_numbers_are_different(self):
        first = Order.objects.create(customer=self.customer, service=self.service)
        second = Order.objects.create(customer=self.customer, service=self.service)
        self.assertNotEqual(first.order_number, second.order_number)

    def test_zero_or_negative_weight_is_rejected(self):
        order = Order.objects.create(customer=self.customer, service=self.service)
        for bad in ('0', '-2'):
            response = self.client.post(reverse('record_weight', args=[order.pk]), {'weight_kg': bad})
            self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.weight_kg, Decimal('0.00'))

    def test_price_from_weight(self):
        order = Order.objects.create(customer=self.customer, service=self.service)
        response = self.client.post(reverse('record_weight', args=[order.pk]), {'weight_kg': '6.5'})
        self.assertRedirects(response, reverse('order_detail', args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('325.00'))

    def test_recording_weight_moves_status_to_priced(self):
        order = Order.objects.create(customer=self.customer, service=self.service)
        self.client.post(reverse('record_weight', args=[order.pk]), {'weight_kg': '6.5'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'PRICED')

    def test_charge_and_discount(self):
        order = Order.objects.create(customer=self.customer, service=self.service, weight_kg=Decimal('6.5'))
        self.client.post(reverse('update_pricing_status', args=[order.pk]), {
            'additional_charge': '50', 'discount_amount': '25', 'status': 'RECEIVED',
        })
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('350.00'))

    def test_negative_charge_or_discount_is_rejected(self):
        order = Order.objects.create(customer=self.customer, service=self.service, weight_kg=Decimal('6.5'))
        response = self.client.post(reverse('update_pricing_status', args=[order.pk]), {
            'additional_charge': '-5', 'discount_amount': '0', 'status': 'RECEIVED',
        })
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse('update_pricing_status', args=[order.pk]), {
            'additional_charge': '0', 'discount_amount': '-5', 'status': 'RECEIVED',
        })
        self.assertEqual(response.status_code, 200)

    def test_total_never_negative(self):
        order = Order.objects.create(customer=self.customer, service=self.service, weight_kg=Decimal('6.5'))
        self.client.post(reverse('update_pricing_status', args=[order.pk]), {
            'additional_charge': '0', 'discount_amount': '1000', 'status': 'RECEIVED',
        })
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('0.00'))

    def test_status_change(self):
        order = Order.objects.create(customer=self.customer, service=self.service)
        self.client.post(reverse('update_pricing_status', args=[order.pk]), {
            'additional_charge': '0', 'discount_amount': '0', 'status': 'WASHING',
        })
        order.refresh_from_db()
        self.assertEqual(order.status, 'WASHING')

    def test_release_and_cancel_cannot_be_set_from_the_pricing_form(self):
        order = Order.objects.create(customer=self.customer, service=self.service)
        for status in ('RELEASED', 'CANCELLED'):
            response = self.client.post(reverse('update_pricing_status', args=[order.pk]), {
                'additional_charge': '0', 'discount_amount': '0', 'status': status,
            })
            self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'RECEIVED')

    def test_new_service_rate_changes_total_on_save(self):
        order = Order.objects.create(customer=self.customer, service=self.service, weight_kg=Decimal('6.5'))
        self.service.price_per_kg = Decimal('60')
        self.service.save()
        order.refresh_from_db()
        order.save()
        self.assertEqual(order.total_price, Decimal('390.00'))

    def test_order_appears_in_customer_history(self):
        order = Order.objects.create(customer=self.customer, service=self.service)
        response = self.client.get(reverse('customer_detail', args=[self.customer.pk]))
        self.assertContains(response, order.get_status_display())

    def test_delete_order(self):
        order = Order.objects.create(customer=self.customer, service=self.service)
        response = self.client.post(reverse('order_delete', args=[order.pk]))
        self.assertRedirects(response, reverse('order_list'))
        self.assertFalse(Order.objects.filter(pk=order.pk).exists())

    def test_order_with_payment_cannot_be_deleted(self):
        order = make_order()
        pay_in_full(order)
        response = self.client.post(reverse('order_delete', args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())


class ProcessingTests(TestCase):
    """Lab 16 to 18: processing steps and the expected release date."""

    def test_expected_release_date_is_calculated_from_the_service(self):
        order = make_order(hours=48)
        self.assertEqual(order.expected_release_date - order.date_received, timedelta(hours=48))

    def test_expected_release_date_typed_by_staff_is_kept(self):
        customer = Customer.objects.create(name='Ana Cruz', phone='09170000000')
        service = Service.objects.create(name='Wash', price_per_kg=Decimal('40'))
        chosen = timezone.now() + timedelta(days=5)
        order = Order.objects.create(customer=customer, service=service, expected_release_date=chosen)
        self.assertEqual(order.expected_release_date, chosen)

    def test_overdue_order_is_identified(self):
        order = make_order()
        Order.objects.filter(pk=order.pk).update(expected_release_date=timezone.now() - timedelta(hours=1))
        order.refresh_from_db()
        self.assertTrue(order.is_overdue)

    def test_order_not_yet_due_is_not_overdue(self):
        order = make_order()
        self.assertFalse(order.is_overdue)

    def test_next_step_buttons_walk_through_the_whole_workflow(self):
        order = make_order()
        expected = ['PRICED', 'CONFIRMED', 'WASHING', 'DRYING', 'FOLDING', 'READY_FOR_RELEASE']
        for status in expected:
            self.client.post(reverse('order_advance', args=[order.pk]))
            order.refresh_from_db()
            self.assertEqual(order.status, status)
        self.assertIsNotNone(order.ready_at)
        # the end of the processing steps: only the release module can finish the order
        self.client.post(reverse('order_advance', args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, 'READY_FOR_RELEASE')
        self.assertEqual(order.status_logs.count(), 7)  # created + 6 steps

    def test_order_without_weight_cannot_move_forward(self):
        customer = Customer.objects.create(name='Ana Cruz', phone='09170000000')
        service = Service.objects.create(name='Wash', price_per_kg=Decimal('40'))
        order = Order.objects.create(customer=customer, service=service)
        self.client.post(reverse('order_advance', args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, 'RECEIVED')

    def test_advance_requires_post(self):
        order = make_order()
        response = self.client.get(reverse('order_advance', args=[order.pk]))
        self.assertEqual(response.status_code, 405)

    def test_cancel_order(self):
        order = make_order()
        response = self.client.post(reverse('order_cancel', args=[order.pk]))
        self.assertRedirects(response, reverse('order_detail', args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, 'CANCELLED')

    def test_order_with_payment_cannot_be_cancelled(self):
        order = make_order()
        pay_in_full(order)
        self.client.post(reverse('order_cancel', args=[order.pk]))
        order.refresh_from_db()
        self.assertNotEqual(order.status, 'CANCELLED')

    def test_closed_order_cannot_be_changed(self):
        order = make_order()
        order.set_status('CANCELLED')
        response = self.client.post(reverse('record_weight', args=[order.pk]), {'weight_kg': '9'})
        self.assertRedirects(response, reverse('order_detail', args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.weight_kg, Decimal('6.50'))


class PaymentTests(TestCase):
    """Lab 19 to 22: billing, payment, validation and receipt."""

    def setUp(self):
        self.order = make_order()  # 6.5 kg at 50 = 325.00
        self.url = reverse('payment_create', args=[self.order.pk])

    def test_bill_page_shows_the_total(self):
        response = self.client.get(reverse('order_bill', args=[self.order.pk]))
        self.assertContains(response, '325.00')

    def test_cash_payment_with_change(self):
        response = self.client.post(self.url, {'payment_method': 'CASH', 'amount_paid': '500', 'reference_no': ''})
        payment = Payment.objects.get()
        self.assertRedirects(response, reverse('payment_receipt', args=[payment.pk]))
        self.assertEqual(payment.amount_applied, Decimal('325.00'))
        self.assertEqual(payment.change, Decimal('175.00'))
        self.assertEqual(payment.status, 'PAID')
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_paid)
        self.assertEqual(self.order.balance_due, Decimal('0.00'))

    def test_partial_payment_leaves_a_balance(self):
        self.client.post(self.url, {'payment_method': 'CASH', 'amount_paid': '100', 'reference_no': ''})
        payment = Payment.objects.get()
        self.assertEqual(payment.status, 'PARTIAL')
        self.assertEqual(payment.change, Decimal('0.00'))
        self.order.refresh_from_db()
        self.assertFalse(self.order.is_paid)
        self.assertEqual(self.order.balance_due, Decimal('225.00'))
        self.assertEqual(self.order.payment_label, 'Partial')

    def test_two_payments_can_clear_the_balance(self):
        self.client.post(self.url, {'payment_method': 'CASH', 'amount_paid': '100', 'reference_no': ''})
        self.client.post(self.url, {'payment_method': 'CASH', 'amount_paid': '225', 'reference_no': ''})
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_paid)
        self.assertEqual(Payment.objects.count(), 2)

    def test_negative_or_zero_amount_is_rejected(self):
        for amount in ('-5', '0'):
            response = self.client.post(self.url, {'payment_method': 'CASH', 'amount_paid': amount, 'reference_no': ''})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_method_is_required(self):
        response = self.client.post(self.url, {'amount_paid': '100', 'reference_no': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.count(), 0)

    def test_card_payment_needs_a_reference_number(self):
        response = self.client.post(self.url, {'payment_method': 'DEBIT', 'amount_paid': '325', 'reference_no': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.count(), 0)
        self.client.post(self.url, {'payment_method': 'DEBIT', 'amount_paid': '325', 'reference_no': 'TXN12345'})
        self.assertEqual(Payment.objects.count(), 1)

    def test_card_payment_cannot_be_more_than_the_balance(self):
        response = self.client.post(self.url, {'payment_method': 'EWALLET', 'amount_paid': '500', 'reference_no': 'REF1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.count(), 0)

    def test_duplicate_payment_is_rejected(self):
        data = {'payment_method': 'CASH', 'amount_paid': '100', 'reference_no': ''}
        self.client.post(self.url, data)
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.count(), 1)

    def test_fully_paid_order_cannot_be_paid_again(self):
        pay_in_full(self.order)
        response = self.client.post(self.url, {'payment_method': 'CASH', 'amount_paid': '50', 'reference_no': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.count(), 1)

    def test_order_without_a_price_cannot_be_paid(self):
        customer = Customer.objects.create(name='Ana Cruz', phone='09170000000')
        service = Service.objects.create(name='Wash', price_per_kg=Decimal('40'))
        order = Order.objects.create(customer=customer, service=service)
        response = self.client.post(reverse('payment_create', args=[order.pk]),
                                    {'payment_method': 'CASH', 'amount_paid': '50', 'reference_no': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.count(), 0)

    def test_receipt_shows_the_details(self):
        self.client.post(self.url, {'payment_method': 'CASH', 'amount_paid': '500', 'reference_no': ''})
        payment = Payment.objects.get()
        response = self.client.get(reverse('payment_receipt', args=[payment.pk]))
        self.assertContains(response, self.order.order_number)
        self.assertContains(response, 'Juan Dela Cruz')
        self.assertContains(response, '175.00')

    def test_changing_the_price_after_payment_updates_the_paid_flag(self):
        pay_in_full(self.order)
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_paid)
        self.order.additional_charge = Decimal('50')
        self.order.save()
        self.order.refresh_from_db()
        self.assertFalse(self.order.is_paid)
        self.assertEqual(self.order.balance_due, Decimal('50.00'))


class ReleaseTests(TestCase):
    """Lab 23 to 25: release validation and confirmation."""

    def setUp(self):
        self.order = make_order()
        self.url = reverse('release_create', args=[self.order.pk])
        self.good = {
            'order_number': self.order.order_number,
            'customer_verified': 'on',
            'released_by': 'Maria Staff',
            'received_by': 'Juan Dela Cruz',
            'notes': '',
        }

    def make_ready_and_paid(self):
        self.order.set_status('READY_FOR_RELEASE')
        pay_in_full(self.order)

    def test_unfinished_laundry_cannot_be_released(self):
        pay_in_full(self.order)  # paid, but the status is still Received
        response = self.client.post(self.url, self.good)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Release.objects.count(), 0)

    def test_unpaid_laundry_cannot_be_released(self):
        self.order.set_status('READY_FOR_RELEASE')
        response = self.client.post(self.url, self.good)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Release.objects.count(), 0)

    def test_wrong_order_number_is_rejected(self):
        self.make_ready_and_paid()
        data = dict(self.good, order_number='ORD-00000000-XXXX')
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Release.objects.count(), 0)

    def test_customer_must_be_verified(self):
        self.make_ready_and_paid()
        data = dict(self.good)
        del data['customer_verified']
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Release.objects.count(), 0)

    def test_staff_name_is_required(self):
        self.make_ready_and_paid()
        response = self.client.post(self.url, dict(self.good, released_by=''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Release.objects.count(), 0)

    def test_paid_and_ready_laundry_is_released(self):
        self.make_ready_and_paid()
        response = self.client.post(self.url, self.good)
        release = Release.objects.get()
        self.assertRedirects(response, reverse('release_detail', args=[release.pk]))
        self.assertRegex(release.release_number, r'^REL-\d{8}-[0-9A-F]{4}$')
        self.assertEqual(release.released_by, 'Maria Staff')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'RELEASED')

    def test_order_cannot_be_released_twice(self):
        self.make_ready_and_paid()
        self.client.post(self.url, self.good)
        response = self.client.post(self.url, self.good)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Release.objects.count(), 1)

    def test_released_order_is_locked(self):
        self.make_ready_and_paid()
        self.client.post(self.url, self.good)
        response = self.client.post(reverse('update_pricing_status', args=[self.order.pk]), {
            'additional_charge': '99', 'discount_amount': '0', 'status': 'RECEIVED',
        })
        self.assertRedirects(response, reverse('order_detail', args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'RELEASED')

    def test_released_order_cannot_be_deleted(self):
        self.make_ready_and_paid()
        self.client.post(self.url, self.good)
        self.client.post(reverse('order_delete', args=[self.order.pk]))
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())

    def test_release_detail_page(self):
        self.make_ready_and_paid()
        self.client.post(self.url, self.good)
        release = Release.objects.get()
        response = self.client.get(reverse('release_detail', args=[release.pk]))
        self.assertContains(response, release.release_number)


class OrderPagesTests(TestCase):
    def test_order_detail_page_opens(self):
        order = make_order()
        response = self.client.get(reverse('order_detail', args=[order.pk]))
        self.assertContains(response, order.order_number)

    def test_order_list_filters(self):
        order = make_order()
        for flt in ('', 'ready', 'due', 'unpaid'):
            response = self.client.get(reverse('order_list'), {'filter': flt})
            self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('order_list'), {'filter': 'unpaid'})
        self.assertContains(response, order.order_number[-4:])


class ReportTests(TestCase):
    """Lab 26 to 31."""

    def setUp(self):
        self.order = make_order()
        pay_in_full(self.order, '500')

    def test_every_report_page_opens(self):
        for name in ('reports_home', 'report_daily', 'report_processing', 'report_revenue',
                     'report_customers', 'report_services', 'dashboard'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)

    def test_bad_dates_fall_back_to_defaults(self):
        for name in ('report_revenue', 'report_customers', 'report_services'):
            response = self.client.get(reverse(name), {'start': 'not-a-date', 'end': '2020-99-99'})
            self.assertEqual(response.status_code, 200, name)
        response = self.client.get(reverse('report_daily'), {'date': 'oops'})
        self.assertEqual(response.status_code, 200)

    def test_daily_report_lists_todays_orders(self):
        response = self.client.get(reverse('report_daily'))
        self.assertContains(response, self.order.order_number)
        self.assertEqual(response.context['totals']['count'], 1)
        self.assertEqual(response.context['totals']['amount'], Decimal('325.00'))

    def test_daily_report_for_another_day_is_empty(self):
        response = self.client.get(reverse('report_daily'), {'date': '2001-01-01'})
        self.assertEqual(response.context['totals']['count'], 0)

    def test_revenue_counts_money_received_not_change(self):
        response = self.client.get(reverse('report_revenue'))
        self.assertEqual(response.context['range_total'], Decimal('325.00'))
        self.assertEqual(response.context['today'], Decimal('325.00'))
        self.assertEqual(response.context['by_method'][0]['name'], 'Cash')

    def test_outstanding_balances_are_listed(self):
        make_order()  # a second order that nobody has paid for
        response = self.client.get(reverse('report_revenue'))
        self.assertEqual(len(response.context['unpaid']), 1)  # the second order is unpaid
        self.assertEqual(response.context['unpaid_total'], Decimal('325.00'))

    def test_service_report_totals(self):
        response = self.client.get(reverse('report_services'))
        row = response.context['rows'][0]
        self.assertEqual(row['orders'], 1)
        self.assertEqual(row['weight'], Decimal('6.50'))
        self.assertEqual(row['billed'], Decimal('325.00'))
        self.assertEqual(row['revenue'], Decimal('325.00'))

    def test_customer_report_counts(self):
        response = self.client.get(reverse('report_customers'))
        self.assertEqual(response.context['total_customers'], 1)
        self.assertEqual(response.context['active_customers'], 1)
        self.assertEqual(response.context['rows'][0]['spent'], Decimal('325.00'))

    def test_processing_report_counts_by_status(self):
        response = self.client.get(reverse('report_processing'))
        counts = {row['code']: row['count'] for row in response.context['rows']}
        self.assertEqual(counts['RECEIVED'], 1)
        self.assertEqual(counts['RELEASED'], 0)

    def test_dashboard_indicators(self):
        order = make_order()  # another customer, unpaid, ready for release
        order.set_status('READY_FOR_RELEASE')
        data = self.client.get(reverse('dashboard')).context['data']
        self.assertEqual(data['customers'], 2)
        self.assertEqual(data['orders_today'], 2)
        self.assertEqual(data['revenue_today'], Decimal('325.00'))
        self.assertEqual(data['ready'], 1)
        self.assertEqual(data['unpaid_count'], 1)
        self.assertEqual(data['popular'][0]['orders'], 2)
