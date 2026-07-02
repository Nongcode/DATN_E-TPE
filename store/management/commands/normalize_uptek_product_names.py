from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from store.models import Category, Inventory, Product
from store.sample_catalog import UPTEK_CATEGORY_DESCRIPTIONS, UPTEK_SAMPLE_PRODUCTS


class Command(BaseCommand):
    help = "Normalize existing products to clear Uptek-style names and searchable content."

    @transaction.atomic
    def handle(self, *args, **options):
        products = list(Product.objects.select_for_update().order_by("id"))
        if not products:
            self.stdout.write(self.style.WARNING("No products found to normalize."))
            return

        normalized_count = 0
        category_cache = {}

        for index, product in enumerate(products):
            item = UPTEK_SAMPLE_PRODUCTS[index % len(UPTEK_SAMPLE_PRODUCTS)]
            category_name = item["category"]
            category = category_cache.get(category_name)
            if category is None:
                category_slug = slugify(category_name)
                category = Category.objects.filter(name=category_name).first()
                if category is None:
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
                category.slug = category_slug
                category.status = "visible"
                category.description = UPTEK_CATEGORY_DESCRIPTIONS.get(category_name, category.description)
                category.save(update_fields=["name", "slug", "status", "description"])
                category_cache[category_name] = category

            sku = item["sku"]
            name = item["name"]
            if index >= len(UPTEK_SAMPLE_PRODUCTS):
                sku = f"{sku}-{index + 1}"
                name = f"{name} #{index + 1}"

            product.category = category
            product.sku = sku
            product.name = name
            product.slug = slugify(f"{sku}-{product.id}".lower())
            product.description = item["description"]
            product.price = Decimal(item["price"])
            product.is_active = True
            product.save(
                update_fields=[
                    "category",
                    "sku",
                    "name",
                    "slug",
                    "description",
                    "price",
                    "is_active",
                ]
            )

            Inventory.objects.update_or_create(
                product=product,
                defaults={"quantity": 12 + (index % 7), "low_stock_threshold": 20},
            )
            normalized_count += 1

        active_category_names = set(category_cache)
        Category.objects.exclude(name__in=active_category_names).update(status="hidden")

        self.stdout.write(
            self.style.SUCCESS(
                f"Normalized {normalized_count} products to Uptek-style searchable names."
            )
        )
