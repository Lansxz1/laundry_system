from django.contrib import admin
from .models import Course, Customer, Service, Order

admin.site.site_header = "Laundry Management System Admin"
admin.site.site_title = "Laundry Admin Portal"
admin.site.index_title = "System Management"

admin.site.register(Course)
admin.site.register(Customer)
admin.site.register(Service)
admin.site.register(Order)