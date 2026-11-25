from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_update, name='customer_update'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),

    # Services
    path('services/', views.service_list, name='service_list'),
    path('services/add/', views.service_create, name='service_create'),
    path('services/<int:pk>/edit/', views.service_update, name='service_update'),
    path('services/<int:pk>/delete/', views.service_delete, name='service_delete'),

    # Orders
    path('orders/', views.order_list, name='order_list'),
    path('orders/add/', views.order_create, name='order_create'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/edit/', views.order_update, name='order_update'),
    path('orders/<int:pk>/delete/', views.order_delete, name='order_delete'),
    path('orders/<int:pk>/weight/', views.record_weight, name='record_weight'),
    path('orders/<int:pk>/pricing/', views.update_pricing_status, name='update_pricing_status'),
    path('orders/<int:pk>/advance/', views.order_advance, name='order_advance'),
    path('orders/<int:pk>/cancel/', views.order_cancel, name='order_cancel'),
    path('orders/<int:pk>/bill/', views.order_bill, name='order_bill'),

    # Payments and release
    path('orders/<int:pk>/pay/', views.payment_create, name='payment_create'),
    path('payments/<int:pk>/receipt/', views.payment_receipt, name='payment_receipt'),
    path('orders/<int:pk>/release/', views.release_create, name='release_create'),
    path('releases/<int:pk>/', views.release_detail, name='release_detail'),

    # Reports
    path('reports/', views.reports_home, name='reports_home'),
    path('reports/daily-orders/', views.report_daily, name='report_daily'),
    path('reports/processing/', views.report_processing, name='report_processing'),
    path('reports/revenue/', views.report_revenue, name='report_revenue'),
    path('reports/customers/', views.report_customers, name='report_customers'),
    path('reports/services/', views.report_services, name='report_services'),
]
