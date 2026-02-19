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
