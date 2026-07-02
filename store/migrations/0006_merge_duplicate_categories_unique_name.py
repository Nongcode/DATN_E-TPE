from django.db import migrations, models
from django.db.models import Count
from django.utils.text import slugify


def merge_duplicate_categories(apps, schema_editor):
    Category = apps.get_model("store", "Category")
    Product = apps.get_model("store", "Product")

    duplicate_names = (
        Category.objects.values("name")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .values_list("name", flat=True)
    )

    for name in duplicate_names:
        categories = list(
            Category.objects.filter(name=name)
            .annotate(product_count=Count("products"))
            .order_by("id")
        )
        if len(categories) < 2:
            continue

        categories.sort(
            key=lambda category: (
                -category.product_count,
                0 if category.status == "visible" else 1,
                category.id,
            )
        )
        keeper = categories[0]
        duplicates = categories[1:]
        duplicate_ids = [category.id for category in duplicates]

        Product.objects.filter(category_id__in=duplicate_ids).update(category=keeper)
        Category.objects.filter(parent_id__in=duplicate_ids).update(parent=keeper)

        if any(category.status == "visible" for category in categories):
            keeper.status = "visible"

        if not keeper.description:
            keeper.description = next(
                (category.description for category in categories if category.description),
                keeper.description,
            )
        if not keeper.image:
            keeper.image = next(
                (category.image for category in categories if category.image),
                keeper.image,
            )

        Category.objects.filter(id__in=duplicate_ids).delete()

        canonical_slug = slugify(name)
        if canonical_slug and not Category.objects.filter(slug=canonical_slug).exclude(id=keeper.id).exists():
            keeper.slug = canonical_slug

        keeper.save(update_fields=["status", "description", "image", "slug"])


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("store", "0005_alter_blog_options_alter_cart_options_and_more"),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_categories, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="category",
            name="name",
            field=models.CharField(max_length=255, unique=True, verbose_name="Tên danh mục"),
        ),
    ]
