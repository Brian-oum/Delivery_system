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

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    if subcategory_slug:
        subcategory = get_object_or_404(SubCategory, slug=subcategory_slug)
        products = products.filter(subcategory=subcategory)

    context = {
        'products': products,
        'category': category,
        'subcategory': subcategory,
    }

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
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart, created = Cart.objects.get_or_create(user=request.user)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product
    )

    if not created:
        cart_item.quantity += 1
        cart_item.save()

    messages.success(request, "Product added to cart.")
    return redirect('cart')

@login_required
def view_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    total = sum(item.total_price() for item in cart.items.all())

    return render(request, 'Deliver/cart.html', {
        'cart': cart,
        'total': total
    })

@login_required
def checkout(request):
    cart = get_object_or_404(Cart, user=request.user)
    items = cart.items.all()

    if not items:
        messages.warning(request, "Your cart is empty.")
        return redirect('product_list')

    total = sum(item.total_price() for item in items)

    order = Order.objects.create(
        user=request.user,
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

    # Clear cart
    items.delete()

    # Send email notification
    send_mail(
        subject="Order Confirmation - Haris Tavern",
        message=f"Your order #{order.id} has been placed successfully.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[request.user.email],
        fail_silently=True,
    )

    messages.success(request, "Order placed successfully!")
    return redirect('orders')

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
