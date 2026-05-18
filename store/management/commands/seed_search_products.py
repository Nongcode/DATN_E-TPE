from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from store.models import Category, Inventory, Product
from store.sample_catalog import UPTEK_CATEGORY_DESCRIPTIONS, UPTEK_SAMPLE_PRODUCTS


class Command(BaseCommand):
    help = "Seed Uptek-style sample products for evaluating smart search quality."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for item in UPTEK_SAMPLE_PRODUCTS:
            category_name = item["category"]
            category_slug = slugify(category_name)
            category = Category.objects.filter(slug=category_slug).first()
            if category is None:
                category, _ = Category.objects.get_or_create(
                    name=category_name,
                    defaults={
                        "slug": category_slug,
                        "status": "visible",
                        "description": UPTEK_CATEGORY_DESCRIPTIONS.get(category_name, ""),
                    },
                )
            category.name = category_name
            category.slug = category.slug or category_slug
            category.status = "visible"
            category.description = UPTEK_CATEGORY_DESCRIPTIONS.get(category_name, category.description)
            category.save(update_fields=["name", "slug", "status", "description"])

            product, created = Product.objects.update_or_create(
                sku=item["sku"],
                defaults={
                    "category": category,
                    "name": item["name"],
                    "slug": slugify(item["sku"].lower()),
                    "description": item["description"],
                    "price": Decimal(item["price"]),
                    "is_active": True,
                },
            )
            Inventory.objects.update_or_create(
                product=product,
                defaults={"quantity": 12, "low_stock_threshold": 4},
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded Uptek smart-search products. Created: {created_count}, updated: {updated_count}."
            )
        )
