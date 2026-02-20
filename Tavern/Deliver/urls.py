# core/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # =========================
    # Authentication
    # =========================
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # =========================
    # Product & Home
    # =========================
    path('', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    # Category filter
    path('category/<slug:category_slug>/',
         views.product_list,
         name='products_by_category'),

    # Subcategory filter
    path('category/<slug:category_slug>/<slug:subcategory_slug>/',
         views.product_list,
         name='products_by_subcategory'),

    # =========================
    # Cart
    # =========================
    # Cart URLs
    path('cart/', views.view_cart, name='cart'),
    path('add-to-cart/<slug:slug>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<slug:slug>/', views.update_cart_quantity, name='update_cart_quantity'),
    path('cart/remove/<slug:slug>/', views.remove_from_cart, name='remove_from_cart'),

    # =========================
    # Checkout & Orders
    # =========================
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.order_history, name='orders'),

    # =========================
    # Ratings
    # =========================
    path('rate-product/<int:pk>/', views.rate_product, name='rate_product'),
    path('rate-website/', views.rate_website, name='rate_website'),

    # =========================
    # Promotions
    # =========================
    path('promotions/', views.promotions_list, name='promotions'),

    # =========================
    # Admin Reports
    # =========================
    #path('admin-reports/', views.admin_reports, name='admin_reports'),
]
