from django.core.management.base import BaseCommand

from store.search import normalize_text
from store.models import Product


KNOWN_BRANDS = [
    "CORGHI",
    "STARTIUM",
    "CROMOBRILL",
    "UNIKA",
    "LAUNCH",
    "BOSCH",
    "MICHELIN",
    "KARCHER",
    "MEGUIAR",
    "ETEK",
]

CAR_MODEL_RULES = {
    "vios": ("Toyota", "Vios"),
    "innova": ("Toyota", "Innova"),
    "fortuner": ("Toyota", "Fortuner"),
    "city": ("Honda", "City"),
    "civic": ("Honda", "Civic"),
    "accent": ("Hyundai", "Accent"),
    "elantra": ("Hyundai", "Elantra"),
    "cerato": ("Kia", "Cerato"),
    "seltos": ("Kia", "Seltos"),
    "ranger": ("Ford", "Ranger"),
    "everest": ("Ford", "Everest"),
    "mazda 3": ("Mazda", "Mazda 3"),
    "cx5": ("Mazda", "CX-5"),
    "cx 5": ("Mazda", "CX-5"),
}

CATEGORY_COMPATIBILITY = [
    (
        ("camera", "cam bien", "obd", "dien", "ac quy"),
        "Toyota, Honda, Hyundai, Kia, Mazda, Ford",
        "Vios, City, Accent, Cerato, Mazda 3, Ranger",
    ),
    (
        ("lop", "nang", "garage", "sua chua"),
        "Toyota, Honda, Hyundai, Kia, Mazda, Ford, Mitsubishi",
        "Vios, City, Accent, Cerato, Mazda 3, Ranger, Xpander",
    ),
    (
        ("rua xe", "detailing", "dong son", "noi that"),
        "Toyota, Honda, Hyundai, Kia, Mazda, Ford, Mitsubishi, Nissan",
        "Vios, City, Accent, Cerato, Mazda 3, Ranger, Xpander, Navara",
    ),
]


def ordered_join(values):
    seen = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return ", ".join(seen)


def infer_brand(product):
    text = f"{product.name} {product.sku or ''} {product.description or ''}".upper()
    for brand in KNOWN_BRANDS:
        if brand in text:
            return "MEGUIAR'S" if brand == "MEGUIAR" else brand
    if product.category and "camera" in normalize_text(product.category.name):
        return "ETEK"
    return "ETEK Garage"


def infer_manufacturer(brand):
    manufacturer_map = {
        "CORGHI": "Corghi S.p.A",
        "STARTIUM": "GYS France",
        "CROMOBRILL": "Ma-Fra Italy",
        "UNIKA": "Unika Professional Care",
        "LAUNCH": "Launch Tech Co., Ltd.",
        "BOSCH": "Robert Bosch GmbH",
        "MICHELIN": "Michelin Lifestyle Limited",
        "KARCHER": "Karcher SE & Co. KG",
        "MEGUIAR'S": "Meguiar's Inc.",
        "ETEK": "ETEK Store",
        "ETEK Garage": "ETEK Garage Equipment",
    }
    return manufacturer_map.get(brand, brand)


def infer_compatibility(product):
    text = normalize_text(
        f"{product.name} {product.sku or ''} {product.description or ''} "
        f"{product.category.name if product.category else ''}"
    )
    car_brands = []
    car_models = []

    for keyword, (car_brand, car_model) in CAR_MODEL_RULES.items():
        if keyword in text:
            car_brands.append(car_brand)
            car_models.append(car_model)

    if not car_brands and not car_models:
        for category_keywords, default_brands, default_models in CATEGORY_COMPATIBILITY:
            if any(keyword in text for keyword in category_keywords):
                car_brands.extend(default_brands.split(", "))
                car_models.extend(default_models.split(", "))
                break

    if not car_brands and not car_models:
        car_brands.extend(["Toyota", "Honda", "Hyundai", "Kia", "Mazda"])
        car_models.extend(["Vios", "City", "Accent", "Cerato", "Mazda 3"])

    return ordered_join(car_brands), ordered_join(car_models)


class Command(BaseCommand):
    help = "Dien metadata thuong hieu, hang san xuat va xe tuong thich cho san pham de cai thien goi y."

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Ghi de metadata hien co neu san pham da co du lieu.",
        )

    def handle(self, *args, **options):
        overwrite = options["overwrite"]
        updated = 0

        for product in Product.objects.select_related("category"):
            brand = infer_brand(product)
            manufacturer = infer_manufacturer(brand)
            car_brands, car_models = infer_compatibility(product)

            fields = []
            if overwrite or not product.brand:
                product.brand = brand
                fields.append("brand")
            if overwrite or not product.manufacturer:
                product.manufacturer = manufacturer
                fields.append("manufacturer")
            if overwrite or not product.compatible_car_brands:
                product.compatible_car_brands = car_brands
                fields.append("compatible_car_brands")
            if overwrite or not product.compatible_car_models:
                product.compatible_car_models = car_models
                fields.append("compatible_car_models")

            if fields:
                product.save(update_fields=fields)
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Da cap nhat metadata goi y cho {updated} san pham."))
