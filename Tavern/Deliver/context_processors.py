from .models import Category, SubCategory
from django.db.models import Prefetch
# Deliver/context_processors.py
from decimal import Decimal
from .models import Cart, CartItem

def cart_total_processor(request):
    total = Decimal('0.00')
    cart = None

    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
    else:
        cart_id = request.session.get('cart_id')
        if cart_id:
            cart = Cart.objects.filter(id=cart_id).first()

    if cart:
        total = sum(Decimal(item.total_price()) for item in cart.items.all())

    return {'cart_total': total}

def categories_processor(request):
    categories = Category.objects.prefetch_related(
        Prefetch(
            'subcategories',
            queryset=SubCategory.objects.order_by('group_name', 'name')
        )
    )
    return {
        'nav_categories': categories
    }