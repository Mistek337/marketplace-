from django.contrib import admin

from .models import (
    Category,
    Product,
    ProductCharacteristic,
    ProductImage,
    SKU,
    SKUCharacteristic,
)


class ProductCharacteristicInline(admin.TabularInline):
    model = ProductCharacteristic
    extra = 0


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class SKUCharacteristicInline(admin.TabularInline):
    model = SKUCharacteristic
    extra = 0


class SKUInline(admin.TabularInline):
    model = SKU
    extra = 0
    show_change_link = True


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'parent')
    list_filter = ('parent',)
    search_fields = ('name',)
    raw_id_fields = ('parent',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'status', 'category')
    list_filter = ('status', 'category')
    search_fields = ('title', 'description')
    inlines = (ProductCharacteristicInline, ProductImageInline, SKUInline)


@admin.register(SKU)
class SKUAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'product', 'price', 'active_quantity')
    list_filter = ('product',)
    inlines = (SKUCharacteristicInline,)
