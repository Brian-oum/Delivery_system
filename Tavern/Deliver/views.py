from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum, Count, Avg
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import *
from .forms import UserRegistrationForm, CustomLoginForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from decimal import Decimal
from django.db import transaction
import requests
import uuid
import json
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.urls import reverse


# =========================
# Registration View
# =========================
def register(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, "Account created successfully! You can now log in.")
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'Deliver/register.html', {'form': form})

# =========================
# Login View
# =========================
def user_login(request):
    if request.method == "POST":
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data['username_or_email']
            password = form.cleaned_data['password']

            try:
                user_obj = User.objects.get(email=username_or_email)
                username = user_obj.username
            except User.DoesNotExist:
                username = username_or_email

            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('product_list')
            else:
                messages.error(request, "Invalid credentials.")
    else:
        form = CustomLoginForm()

    return render(request, 'Deliver/login.html', {'form': form})

# =========================
# Logout View
# =========================
def user_logout(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')


# =========================
# Helper: get cart (guest or user)
# =========================
def get_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
        cart_id = request.session.get('cart_id')
        if cart_id:
            cart = Cart.objects.filter(id=cart_id).first()
            if not cart:
                cart = Cart.objects.create()
                request.session['cart_id'] = cart.id
        else:
            cart = Cart.objects.create()
            request.session['cart_id'] = cart.id
    return cart


# =========================
# Product Views
# =========================
def product_list(request, category_slug=None, subcategory_slug=None):
    products = Product.objects.all()
    category = None
    subcategory = None
    
    view_filter = request.GET.get('filter')
    search_query = request.GET.get('q')  # get search query

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    if subcategory_slug:
        subcategory = get_object_or_404(SubCategory, slug=subcategory_slug)
        products = products.filter(subcategory=subcategory)

    # Search filtering
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    popular_products = None
    new_products = None

    if not category and not subcategory and not search_query:
        if view_filter == 'popular':
            popular_products = Product.objects.filter(feature='popular')
            new_products = None
            products = None
        else:
            popular_products = Product.objects.filter(feature='popular')[:6]
            new_products = Product.objects.filter(feature='new').order_by('-created_at')[:6]

    context = {
        'products': products,
        'category': category,
        'subcategory': subcategory,
        'popular_products': popular_products,
        'new_products': new_products,
        'view_filter': view_filter,
        'search_query': search_query,
    }

    return render(request, 'Deliver/product_list.html', context)

def product_detail(request, slug):
    # Fetch the product or return 404 if not found
    product = get_object_or_404(Product, slug=slug)
    
    # Optional: Get related products from the same subcategory/category
    # This is great for a "You may also like" section later
    related_products = Product.objects.filter(
        subcategory=product.subcategory
    ).exclude(id=product.id)[:4]

    # Fetch ratings for this specific product
    ratings = product.ratings.all().order_by('-created_at')
    
    # Calculate average rating (optional logic)
    avg_rating = 0
    if ratings.exists():
        avg_rating = sum(r.rating for r in ratings) / ratings.count()

    context = {
        'product': product,
        'related_products': related_products,
        'ratings': ratings,
        'avg_rating': avg_rating,
    }
    
    return render(request, 'Deliver/product_detail.html', context)

# =========================
# Cart Views (Guests & Users)
# =========================
def add_to_cart(request, slug):
    product = get_object_or_404(Product, slug=slug)
    cart = get_cart(request)

    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        cart_item.quantity += 1
        cart_item.save()

    messages.success(request, f"{product.name} added to cart.")
    return redirect('cart')


def view_cart(request):
    cart = get_cart(request)
    items = cart.items.all()

    total = sum(Decimal(item.total_price()) for item in items)
    vat_rate = Decimal('0.16')
    delivery_threshold = Decimal('15000')

    subtotal_ex_vat = (total / (Decimal('1') + vat_rate)) if total > 0 else Decimal('0')
    vat_amount = total - subtotal_ex_vat

    progress_percent = (total / delivery_threshold * Decimal('100')) if total > 0 else Decimal('0')
    progress_percent = min(progress_percent, Decimal('100'))

    context = {
        'cart': cart,
        'items': items,
        'total': total,
        'subtotal_ex_vat': subtotal_ex_vat,
        'vat_amount': vat_amount,
        'progress_percent': progress_percent,
        'delivery_threshold': delivery_threshold,
    }

    return render(request, 'Deliver/cart.html', context)


def update_cart_quantity(request, slug):
    if request.method == 'POST':
        action = request.POST.get('action')
        cart = get_cart(request)
        cart_item = get_object_or_404(CartItem, cart=cart, product__slug=slug)

        if action == 'increase':
            cart_item.quantity += 1
            cart_item.save()
            messages.success(request, f'Increased quantity for {cart_item.product.name}.')
        elif action == 'decrease':
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()
                messages.success(request, f'Decreased quantity for {cart_item.product.name}.')
            else:
                cart_item.delete()
                messages.success(request, f'{cart_item.product.name} removed from cart.')

    return redirect('cart')


def remove_from_cart(request, slug):
    if request.method == 'POST':
        cart = get_cart(request)
        cart_item = get_object_or_404(CartItem, cart=cart, product__slug=slug)
        cart_item.delete()
        messages.success(request, f'{cart_item.product.name} removed from cart.')

    return redirect('cart')


# =========================
# Checkout (Guests & Logged-in Users with IntaSend)
# =========================
# views.py
def checkout(request):
    cart = get_cart(request)
    items = cart.items.all()

    if not items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect('product_list')

    total = sum(Decimal(item.total_price()) for item in items)
    vat_rate = Decimal('0.16')
    subtotal_ex_vat = total / (Decimal('1') + vat_rate)
    vat_amount = total - subtotal_ex_vat

    if request.method == 'POST':
        # Collect user info
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        order_notes = request.POST.get('order_notes', '')

        building_name = request.POST.get('building_name')
        door_number = request.POST.get('door_number')
        latitude = request.POST.get('latitude') or None
        longitude = request.POST.get('longitude') or None

        payment_method = request.POST.get('payment')

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                notes=order_notes,
                building_name=building_name,
                door_number=door_number,
                latitude=latitude,
                longitude=longitude,
                total_amount=total,
                status='pending'
            )

            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )

            # Clear guest session cart
            if not request.user.is_authenticated:
                del request.session['cart_id']

            items.delete()

        # Redirect to IntaSend payment page if chosen
        if payment_method == 'intasend':
            return redirect('intasend_payment', order_id=order.id)

        # Otherwise, handle other payment methods (e.g., M-Pesa)
        messages.success(request, "Order placed successfully!")
        return redirect('orders')

    context = {
        'cart': cart,
        'items': items,
        'total': total,
        'subtotal_ex_vat': subtotal_ex_vat,
        'vat_amount': vat_amount,
    }

    return render(request, 'Deliver/checkout.html', context)

#

def intasend_payment_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # =========================
    # Development: Simulate Payment
    # =========================
    if settings.DEBUG:
        simulate_payment(order)
        messages.success(request, "Payment simulated successfully (DEV MODE).")
        return redirect("payment_wait", order_id=order.id)

    # =========================
    # Production / Sandbox STK Push
    # =========================
    if request.method == "POST":
        phone = request.POST.get("phone")
        if not phone:
            messages.error(request, "Phone number is required to initiate payment.")
            return redirect("intasend_payment", order_id=order.id)

        payload = {
            "amount": float(order.total_amount),
            "phone_number": phone,
            "currency": "KES",
            "api_ref": f"ORDER-{order.id}", 
            "callback_url": request.build_absolute_uri("/intasend/webhook/"),
        }

        headers = {
            "Authorization": f"Bearer {settings.INTASEND_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                "https://sandbox.intasend.com/api/v1/payment/mpesa-stk-push/",
                json=payload,
                headers=headers,
                timeout=15
            )
            print(f"Status Code: {response.status_code}")
            data = response.json()

            if response.status_code in [200, 201, 202]:
                order.status = "payment_initiated"
                order.save()
                messages.info(request, "Please check your phone for the M-Pesa STK prompt.")
                return redirect("payment_wait", order_id=order.id)
            else:
                error_msg = data.get("errors", "Request failed. Verify your phone number.")
                messages.error(request, f"Payment error: {error_msg}")
                return redirect("intasend_payment", order_id=order.id)

        except requests.RequestException as e:
            messages.error(request, f"Connection to payment gateway failed: {str(e)}")
            return redirect("intasend_payment", order_id=order.id)

    return render(request, "Deliver/mpesa_checkout.html", {"order": order})

def check_payment_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return JsonResponse({"status": order.status})
    
def payment_wait(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'Deliver/payment_wait.html', {'order': order})

@csrf_exempt
def intasend_webhook(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # IntaSend usually sends 'invoice_id' or 'api_ref'
            reference = data.get('api_ref') 
            state = data.get('state') # IntaSend often uses 'state': 'COMPLETE'

            if reference and reference.startswith("ORDER-"):
                order_id = int(reference.split('-')[1])
                order = Order.objects.get(id=order_id)

                if state == 'COMPLETE':
                    order.status = 'paid'
                elif state == 'FAILED':
                    order.status = 'payment_failed'
                order.save()
            
            return HttpResponse(status=200) # Tell IntaSend "Got it!"
        except Exception as e:
            print(f"Webhook error: {e}")
            return HttpResponse(status=400) # Something went wrong
            
    return HttpResponse(status=405) # Method not allowed

def order_history(request):
    if not request.user.is_authenticated:
        messages.warning(request, "Please log in to view your orders.")
        return redirect(f"{reverse('login')}?next={request.path}")

    user_orders = Order.objects.filter(user=request.user)

    guest_cart_id = request.session.get('cart_id')
    if guest_cart_id:
        guest_orders = Order.objects.filter(user__isnull=True, id__in=guest_cart_id)
        guest_orders.update(user=request.user)
        user_orders = user_orders | guest_orders
        del request.session['cart_id']

    orders = user_orders.order_by('-created_at')

    # Annotate each order item with a flag if the user has already rated it
    for order in orders:
        for item in order.items.all():
            item.rated_by_user = item.product.ratings.filter(user=request.user).exists()

    return render(request, 'Deliver/orders.html', {'orders': orders})
# =========================
# Ratings (logged in only)
# =========================

def rate_product(request, pk):
    if not request.user.is_authenticated:
        messages.warning(request, "Please log in to rate products.")
        return redirect('login')

    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        rating = int(request.POST.get('rating'))
        comment = request.POST.get('comment', '')

        # Check if user has already rated
        existing_rating = ProductRating.objects.filter(product=product, user=request.user).first()
        if existing_rating:
            existing_rating.rating = rating
            existing_rating.comment = comment
            existing_rating.save()
            messages.success(request, f"Updated your rating for {product.name}.")
        else:
            ProductRating.objects.create(
                product=product,
                user=request.user,
                rating=rating,
                comment=comment
            )
            messages.success(request, f"Thank you for rating {product.name}!")

        # Redirect back to where the request came from (orders page or product page)
        return redirect(request.META.get('HTTP_REFERER', 'orders'))

    return render(request, 'Deliver/rate_product.html', {'product': product})

def rate_website(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # Only allow rating if payment is successful
    if order.status != "paid":
        messages.error(request, "You can only rate after a successful payment.")
        return redirect('orders')

    # Prevent multiple ratings per user per order (optional)
    if WebsiteRating.objects.filter(user=request.user).exists():
        messages.info(request, "You have already rated our website.")
        return redirect('orders')

    if request.method == "POST":
        rating_value = request.POST.get("rating")
        comment = request.POST.get("comment", "")
        if rating_value:
            WebsiteRating.objects.create(
                user=request.user,
                rating=int(rating_value),
                comment=comment
            )
            messages.success(request, "Thank you for your feedback!")
            return redirect('orders')
        else:
            messages.error(request, "Please select a rating before submitting.")

    return render(request, "Deliver/rate_website.html", {"order": order})

# =========================
# Promotions
# =========================
def promotions_list(request):
    promotions = Promotion.objects.filter(
        active=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    )

    return render(request, 'Deliver/promotions.html', {'promotions': promotions})


def simulate_payment(order):
    """
    Marks an order as paid for development purposes without calling IntaSend.
    """
    order.status = "paid"
    order.payment_reference = f"FAKE-{order.id}"  # fake payment reference
    order.save()
    print(f"[SIMULATION] Order {order.id} marked as PAID.")