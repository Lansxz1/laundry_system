from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    
    # Customer routes
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    
    # Service routes
    path('services/', views.service_list, name='service_list'),
    path('services/add/', views.service_create, name='service_create'),
    path('services/<int:pk>/edit/', views.service_update, name='service_update'),
    path('services/<int:pk>/delete/', views.service_delete, name='service_delete'),
]