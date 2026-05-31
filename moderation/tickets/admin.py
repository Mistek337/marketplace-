from django.contrib import admin

from tickets.models import BlockingReason, Moderator, Ticket


@admin.register(Moderator)
class ModeratorAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'role', 'is_active')
    search_fields = ('email',)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'product_id', 'status', 'assigned_moderator', 'decision_at')
    list_filter = ('status',)
    search_fields = ('id', 'product_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(BlockingReason)
class BlockingReasonAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'hard_block', 'is_active')
    list_filter = ('hard_block', 'is_active')
