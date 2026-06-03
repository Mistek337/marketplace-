from django.contrib import admin

from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    raw_id_fields = ("sku",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "seller_id", "status", "created_at")
    list_filter = ("status",)
    inlines = (InvoiceItemInline,)
