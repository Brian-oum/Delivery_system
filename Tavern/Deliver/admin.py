from django.contrib import admin

# Register your models here.
from .models import *

admin.site.register(Product)
admin.site.register(Order)
admin.site.register(ProductRating)
admin.site.register(Promotion)
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {"slug": ("name",)}

@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'slug')
    list_filter = ('category',)
    prepopulated_fields = {"slug": ("name",)}
@admin.register(WebsiteRating)
class WebsiteRatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'rating', 'comment', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__username', 'comment')

@admin.register(OrderTracking)
class OrderTrackingAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'driver_latitude', 'driver_longitude', 'updated_at')
    list_filter = ('status', 'updated_at')
    search_fields = ('order__id',)
    readonly_fields = ('updated_at',)  # Updated automatically