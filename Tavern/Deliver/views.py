from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Avg
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import  *
from .forms import UserRegistrationForm, CustomLoginForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from decimal import Decimal  # Add this import at the top

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
# Login View (username or email)
# =========================
def user_login(request):
    if request.method == "POST":
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data['username_or_email']
            password = form.cleaned_data['password']

            # Try to get username from email
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


def product_list(request, category_slug=None, subcategory_slug=None):
    products = Product.objects.all()
    category = None
    subcategory = None
    
    # Check for the view_all filter
    view_filter = request.GET.get('filter')

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    if subcategory_slug:
        subcategory = get_object_or_404(SubCategory, slug=subcategory_slug)
        products = products.filter(subcategory=subcategory)

    popular_products = None
    new_products = None

    if not category and not subcategory:
        # If user clicked "View All" for popular
        if view_filter == 'popular':
            popular_products = Product.objects.filter(feature='popular')
            new_products = None  # Hide new products
            products = None      # Hide main grid
        else:
            # Standard homepage view
            popular_products = Product.objects.filter(feature='popular')[:6]
            new_products = Product.objects.filter(feature='new').order_by('-created_at')[:6]

    context = {
        'products': products,
        'category': category,
        'subcategory': subcategory,
        'popular_products': popular_products,
        'new_products': new_products,
        'view_filter': view_filter, # Send to template to toggle UI
    }

    return render(request, 'Deliver/product_list.html', context)
    return render(request, 'Deliver/product_list.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    ratings = product.ratings.all()
    average_rating = ratings.aggregate(Avg('rating'))['rating__avg']

    return render(request, 'Deliver/product_detail.html', {
        'product': product,
        'ratings': ratings,
        'average_rating': average_rating
    })

@login_required
def add_to_cart(request, slug):
    product = get_object_or_404(Product, slug=slug)
    cart, _ = Cart.objects.get_or_create(user=request.user)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product
    )

    if not created:
        cart_item.quantity += 1
        cart_item.save()

    messages.success(request, f"{product.name} added to cart.")
    return redirect('cart')

# -----------------------------
# View cart
# -----------------------------
@login_required
def view_cart(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    # Ensure total is Decimal
    total = sum(Decimal(item.total_price()) for item in cart.items.all())
    vat_rate = Decimal('0.16')
    delivery_threshold = Decimal('15000')

    subtotal_ex_vat = (total / (Decimal('1') + vat_rate)) if total > 0 else Decimal('0')
    vat_amount = total - subtotal_ex_vat

    progress_percent = (total / delivery_threshold * Decimal('100')) if total > 0 else Decimal('0')
    progress_percent = min(progress_percent, Decimal('100'))

    context = {
        'cart': cart,
        'total': total,
        'subtotal_ex_vat': subtotal_ex_vat,
        'vat_amount': vat_amount,
        'progress_percent': progress_percent,
        'delivery_threshold': delivery_threshold,
    }

    return render(request, 'Deliver/cart.html', context)


# -----------------------------
# Update quantity (+/-)
# -----------------------------
@login_required
def update_cart_quantity(request, slug):
    if request.method == 'POST':
        action = request.POST.get('action')
        cart_item = get_object_or_404(
            CartItem,
            cart__user=request.user,
            product__slug=slug 
        )

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


# -----------------------------
# Remove item from cart
# -----------------------------
@login_required
def remove_from_cart(request, slug):
    if request.method == 'POST':
        cart_item = get_object_or_404(
            CartItem,
            cart__user=request.user,
            slug=slug
        )
        cart_item.delete()
        messages.success(request, f'{cart_item.product.name} removed from cart.')

    return redirect('cart')

from decimal import Decimal
from django.db import transaction

@login_required
def checkout(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.all()

    if not items:
        messages.warning(request, "Your cart is empty.")
        return redirect('product_list')

    # Financial Calculations for the Sidebar Summary
    total = sum(Decimal(item.total_price()) for item in items)
    vat_rate = Decimal('0.16')
    subtotal_ex_vat = total / (Decimal('1') + vat_rate)
    vat_amount = total - subtotal_ex_vat

    if request.method == 'POST':
        # 1. Capture Form Data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        order_notes = request.POST.get('order_notes', '')
        payment_method = request.POST.get('payment')

        # 2. Use a transaction to ensure Order + Items are created together
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                total_amount=total,
                status='pending',
                # Assuming you add these fields to your Order model:
                # first_name=first_name,
                # phone=phone,
                # notes=order_notes
            )

            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )

            # 3. Clear cart AFTER order is created
            items.delete()

        # 4. Handle Payment Logic (e.g., trigger M-Pesa STK Push if selected)
        if payment_method == 'mpesa':
            # This is where you'd call your M-Pesa function
            # initiate_stk_push(phone, total)
            pass

        # 5. Send Email
        send_mail(
            subject="Order Confirmation - Haris Tavern",
            message=f"Hi {first_name}, Your order #{order.id} has been placed.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )

        messages.success(request, "Order placed successfully!")
        return redirect('orders')

    # GET request: Just show the form and summary
    context = {
        'cart': cart,
        'items': items,
        'total': total,
        'subtotal_ex_vat': subtotal_ex_vat,
        'vat_amount': vat_amount,
    }
    return render(request, 'Deliver/checkout.html', context)

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'Deliver/orders.html', {'orders': orders})

@login_required
def rate_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        rating = int(request.POST.get('rating'))
        comment = request.POST.get('comment')

        ProductRating.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            comment=comment
        )

        messages.success(request, "Thank you for your feedback!")
        return redirect('product_detail', pk=pk)

    return render(request, 'Deliver/rate_product.html', {'product': product})

@login_required
def rate_website(request):
    if request.method == "POST":
        rating = int(request.POST.get('rating'))
        comment = request.POST.get('comment')

        WebsiteRating.objects.create(
            user=request.user,
            rating=rating,
            comment=comment
        )

        messages.success(request, "Thanks for rating our website!")
        return redirect('product_list')

    return render(request, 'Deliver/rate_website.html')

def promotions_list(request):
    promotions = Promotion.objects.filter(
        active=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    )

    return render(request, 'Deliver/promotions.html', {
        'promotions': promotions
    })
