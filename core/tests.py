from django.test import TestCase
from django.urls import reverse

from .models import Course, Customer


class CourseCrudTests(TestCase):
    """Step 2: Create, Read, Update, Delete for Courses."""

    def test_create_course(self):
        response = self.client.post(reverse('course_create'), {'course_name': 'BSIT'})
        self.assertRedirects(response, reverse('course_list'))
        self.assertTrue(Course.objects.filter(course_name='BSIT').exists())

    def test_read_course_list(self):
        Course.objects.create(course_name='BSBA')
        response = self.client.get(reverse('course_list'))
        self.assertContains(response, 'BSBA')

    def test_update_course(self):
        course = Course.objects.create(course_name='BSED')
        response = self.client.post(
            reverse('course_update', args=[course.pk]), {'course_name': 'BEED'}
        )
        self.assertRedirects(response, reverse('course_list'))
        course.refresh_from_db()
        self.assertEqual(course.course_name, 'BEED')

    def test_delete_course(self):
        course = Course.objects.create(course_name='BSN')
        response = self.client.post(reverse('course_delete', args=[course.pk]))
        self.assertRedirects(response, reverse('course_list'))
        self.assertFalse(Course.objects.filter(pk=course.pk).exists())

    def test_duplicate_course_is_rejected(self):
        Course.objects.create(course_name='BSIT')
        response = self.client.post(reverse('course_create'), {'course_name': 'BSIT'})
        self.assertEqual(response.status_code, 200)  # form is shown again with an error
        self.assertEqual(Course.objects.filter(course_name='BSIT').count(), 1)


class CustomerCourseTests(TestCase):
    """Steps 3 to 6: the Course field on the customer form."""

    def setUp(self):
        self.bsit = Course.objects.create(course_name='BSIT')
        self.bsba = Course.objects.create(course_name='BSBA')

    def test_dropdown_loads_courses_from_database(self):
        response = self.client.get(reverse('customer_create'))
        self.assertContains(response, 'BSIT')
        self.assertContains(response, 'BSBA')

    def test_new_course_appears_in_dropdown_automatically(self):
        Course.objects.create(course_name='BEED')
        response = self.client.get(reverse('customer_create'))
        self.assertContains(response, 'BEED')

    def test_selected_course_is_saved(self):
        self.client.post(reverse('customer_create'), {
            'name': 'John Doe',
            'phone': '09171234567',
            'course': self.bsit.pk,
        })
        customer = Customer.objects.get(name='John Doe')
        self.assertEqual(customer.course, self.bsit)

    def test_course_is_displayed_in_records(self):
        Customer.objects.create(name='Maria Santos', phone='09170000000', course=self.bsba)
        response = self.client.get(reverse('customer_list'))
        self.assertContains(response, 'Maria Santos')
        self.assertContains(response, 'BSBA')

    def test_course_is_optional(self):
        response = self.client.post(reverse('customer_create'), {
            'name': 'Ana Cruz',
            'phone': '09175555555',
        })
        self.assertRedirects(response, reverse('customer_list'))

    def test_deleting_a_course_keeps_the_customer(self):
        customer = Customer.objects.create(name='James Reyes', phone='09176666666', course=self.bsit)
        self.client.post(reverse('course_delete', args=[self.bsit.pk]))
        customer.refresh_from_db()
        self.assertIsNone(customer.course)