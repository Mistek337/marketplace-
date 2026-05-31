"""Повтор unreserve для заказов в CANCEL_PENDING (cron / manual)."""

from django.core.management.base import BaseCommand

from orders.services import retry_cancel_unreserve_for_pending_orders


class Command(BaseCommand):
    help = "Retry B2B unreserve for orders stuck in CANCEL_PENDING."

    def handle(self, *args, **options):
        count = retry_cancel_unreserve_for_pending_orders()
        self.stdout.write(self.style.SUCCESS(f"Finalized {count} cancelled order(s)."))
