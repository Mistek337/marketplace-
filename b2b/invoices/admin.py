from django.contrib import admin

from .models import Invoice, InvoiceLine


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    raw_id_fields = ('sku',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'created_at', 'note_short')
    list_filter = ('status',)
    inlines = (InvoiceLineInline,)

    @admin.display(description='note')
    def note_short(self, obj: Invoice) -> str:
        return (obj.note[:60] + '…') if len(obj.note) > 60 else obj.note
