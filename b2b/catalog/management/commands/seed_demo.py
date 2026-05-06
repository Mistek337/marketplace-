"""
Идемпотентное наполнение каталога B2B для локальной разработки и ревью в Docker.

Запуск из контейнера:
  docker compose exec b2b python manage.py seed_demo

Локально (venv + Postgres B2B):
  cd b2b && python manage.py seed_demo
"""

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, Product, ProductCharacteristic, ProductImage, SKU
from sellers.models import Seller

# Стабильные маркеры — повторный запуск обновляет те же сущности.
SEED_PRODUCT_TITLE = "[seed] NeoMarket Demo Phone"
DEMO_SELLER_EMAIL = "demo-seller@neomarket.local"
DEMO_SELLER_PASSWORD = "demo-demo-demo"


class Command(BaseCommand):
    help = "Создаёт демо-категории, продавца, товар MODERATED и 2 SKU (для Docker/ревью)."

    @transaction.atomic
    def handle(self, *args, **options):
        seller, _ = Seller.objects.update_or_create(
            email=DEMO_SELLER_EMAIL,
            defaults={
                "password": make_password(DEMO_SELLER_PASSWORD),
                "first_name": "Demo",
                "last_name": "Seller",
                "middle_name": "",
                "company_name": "NeoMarket Demo",
                "phone": "",
            },
        )

        electronics, _ = Category.objects.get_or_create(
            name="Электроника",
            parent=None,
        )
        smartphones, _ = Category.objects.get_or_create(
            name="Смартфоны",
            parent=electronics,
        )

        product, created = Product.objects.update_or_create(
            title=SEED_PRODUCT_TITLE,
            defaults={
                "description": "Демо-товар из seed_demo (виден на витрине при статусе MODERATED).",
                "category": smartphones,
                "status": Product.Status.MODERATED,
                "deleted": False,
                "seller_id": seller.id,
            },
        )

        ProductImage.objects.filter(product=product).delete()
        ProductCharacteristic.objects.filter(product=product).delete()
        ProductImage.objects.create(
            product=product,
            url="https://via.placeholder.com/400x400?text=NeoMarket+Demo",
            ordering=0,
        )
        ProductCharacteristic.objects.create(
            product=product,
            name="Бренд",
            value="Demo",
        )

        product.skus.all().delete()
        SKU.objects.create(
            product=product,
            name="128 GB, чёрный",
            price=8_999_000,
            cost_price=7_500_000,
            discount=0,
            image="https://via.placeholder.com/200x200?text=128GB",
            active_quantity=25,
            reserved_quantity=0,
        )
        SKU.objects.create(
            product=product,
            name="256 GB, белый",
            price=10_999_000,
            cost_price=9_300_000,
            discount=500_000,
            image="https://via.placeholder.com/200x200?text=256GB",
            active_quantity=12,
            reserved_quantity=0,
        )

        verb = "Создан" if created else "Обновлён"
        self.stdout.write(self.style.SUCCESS(f"{verb} товар «{SEED_PRODUCT_TITLE}» (id={product.id})"))
        self.stdout.write(f"  Продавец для API: {DEMO_SELLER_EMAIL} / {DEMO_SELLER_PASSWORD}")
        self.stdout.write(f"  Категория: Смартфоны (id={smartphones.id})")
