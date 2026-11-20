from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Customer, Service, Order


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


class ServiceTests(TestCase):
    """UT-04 to UT-07."""

    def test_add_service(self):
        response = self.client.post(reverse('service_create'), {
            'name': 'Wash and Fold', 'description': '', 'price_per_kg': '50', 'is_active': 'on',
        })
        self.assertRedirects(response, reverse('service_list'))
        self.assertTrue(Service.objects.filter(name='Wash and Fold').exists())

    def test_negative_rate_is_rejected(self):
        response = self.client.post(reverse('service_create'), {
            'name': 'Bad Rate', 'description': '', 'price_per_kg': '-10', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Service.objects.filter(name='Bad Rate').exists())

    def test_duplicate_name_is_rejected(self):
        Service.objects.create(name='Wash and Fold', price_per_kg=Decimal('50'))
        response = self.client.post(reverse('service_create'), {
            'name': 'Wash and Fold', 'description': '', 'price_per_kg': '60', 'is_active': 'on',
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
        self.assertRedirects(response, reverse('order_list'))
        self.assertEqual(Order.objects.count(), 1)

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

    def test_charge_and_discount(self):
        order = Order.objects.create(customer=self.customer, service=self.service, weight_kg=Decimal('6.5'))
        self.client.post(reverse('update_pricing_status', args=[order.pk]), {
            'additional_charge': '50', 'discount_amount': '25', 'status': 'RECEIVED',
        })
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('350.00'))

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