from datetime import timedelta
from decimal import Decimal
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from store.models import Customer, Inventory, Order, OrderItem, Product, Voucher


CUSTOMER_NAMES = [
    "Nguyễn Minh Anh",
    "Trần Quốc Bảo",
    "Lê Hoàng Nam",
    "Phạm Đức Long",
    "Vũ Gia Hân",
    "Đỗ Thành Đạt",
    "Hoàng Tuấn Kiệt",
    "Bùi Khánh Linh",
    "Ngô Nhật Minh",
    "Đặng Thanh Tùng",
    "Phan Hải Yến",
    "Mai Quang Huy",
    "Tạ Hữu Phước",
    "Dương Bảo Ngọc",
    "Cao Anh Khoa",
    "Lương Thùy Dương",
    "Hà Việt Hoàng",
    "Chu Minh Quân",
    "Đinh Phương Thảo",
    "Trịnh An Nhiên",
    "Đào Công Vinh",
    "Kiều Thanh Mai",
    "Lâm Gia Bách",
    "Tô Khánh An",
]

STREETS = [
    "Cầu Giấy, Hà Nội",
    "Thanh Xuân, Hà Nội",
    "Nam Từ Liêm, Hà Nội",
    "Hải Châu, Đà Nẵng",
    "Quận 1, TP. Hồ Chí Minh",
    "Bình Thạnh, TP. Hồ Chí Minh",
    "Ninh Kiều, Cần Thơ",
    "Lê Chân, Hải Phòng",
]


class Command(BaseCommand):
    help = "Seed realistic demo customers, orders, order items, vouchers, and inventory for dashboard statistics."

    def add_arguments(self, parser):
        parser.add_argument("--customers", type=int, default=24, help="Number of demo customers to create.")
        parser.add_argument("--orders", type=int, default=96, help="Number of demo orders to create.")
        parser.add_argument("--reset-demo", action="store_true", help="Delete existing demo customers/orders before seeding.")

    @transaction.atomic
    def handle(self, *args, **options):
        customer_count = options["customers"]
        order_count = options["orders"]
        reset_demo = options["reset_demo"]

        if customer_count < 1 or order_count < 1:
            raise CommandError("--customers and --orders must be positive numbers.")

        products = list(Product.objects.filter(is_active=True).order_by("id"))
        if not products:
            raise CommandError("No active products found. Seed products before seeding dashboard demo data.")

        User = get_user_model()
        demo_users = User.objects.filter(username__startswith="demo_customer_")
        if demo_users.exists() and not reset_demo:
            self.stdout.write(
                self.style.WARNING(
                    "Demo business data already exists. Use --reset-demo to rebuild it."
                )
            )
            return

        if reset_demo:
            deleted_users = demo_users.count()
            demo_users.delete()
            self.stdout.write(f"Deleted {deleted_users} existing demo users and related demo data.")

        rng = random.Random(20260702)
        now = timezone.now()
        start_date = now - timedelta(days=180)

        customers = []
        for index in range(customer_count):
            full_name = CUSTOMER_NAMES[index % len(CUSTOMER_NAMES)]
            username = f"demo_customer_{index + 1:03d}"
            email = f"demo.customer.{index + 1:03d}@example.com"
            phone = f"09{index + 1:08d}"[:10]
            user = User.objects.create_user(
                username=username,
                email=email,
                password="Demo@123456",
                first_name=full_name.split()[0],
                last_name=" ".join(full_name.split()[1:]),
            )
            customer = Customer.objects.create(
                user=user,
                full_name=full_name,
                email=email,
                phone_number=phone,
                address=f"{12 + index} Đường Demo, {STREETS[index % len(STREETS)]}",
                date_of_birth=(now.date() - timedelta(days=365 * (24 + index % 18) + index * 9)),
            )
            customers.append(customer)

        for index, product in enumerate(products):
            if index % 9 == 0:
                quantity = rng.randint(0, 4)
                threshold = rng.randint(8, 15)
            elif index % 5 == 0:
                quantity = rng.randint(5, 12)
                threshold = rng.randint(12, 20)
            else:
                quantity = rng.randint(18, 95)
                threshold = rng.randint(8, 18)
            Inventory.objects.update_or_create(
                product=product,
                defaults={"quantity": quantity, "low_stock_threshold": threshold},
            )

        vouchers = []
        for index, customer in enumerate(customers):
            if index % 3 == 0:
                voucher = Voucher.objects.create(
                    code=f"DEMO{index + 1:03d}",
                    customer=customer,
                    discount_amount=Decimal(rng.choice([50000, 100000, 150000, 200000])),
                    valid_until=now + timedelta(days=rng.randint(7, 60)),
                    is_used=index % 2 == 0,
                )
                vouchers.append(voucher)

        status_pool = ["Shipped"] * 42 + ["Shipping"] * 18 + ["Confirmed"] * 18 + ["Pending"] * 12 + ["Cancelled"] * 6
        created_orders = 0
        created_items = 0

        for index in range(order_count):
            customer = rng.choice(customers)
            selected_products = rng.sample(products, k=rng.randint(1, min(4, len(products))))
            order_date = start_date + timedelta(days=rng.randint(0, 180), hours=rng.randint(8, 20), minutes=rng.randint(0, 59))
            status = rng.choice(status_pool)
            voucher = rng.choice(vouchers) if vouchers and index % 7 == 0 else None

            total_amount = Decimal("0")
            order = Order.objects.create(
                customer=customer,
                voucher=voucher,
                total_amount=Decimal("0"),
                status=status,
            )
            Order.objects.filter(pk=order.pk).update(created_at=order_date)
            order.created_at = order_date

            for product in selected_products:
                quantity = rng.randint(1, 3)
                price = product.price or Decimal("0")
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    price=price,
                    quantity=quantity,
                )
                total_amount += price * quantity
                created_items += 1

            if voucher and status != "Cancelled":
                total_amount = max(Decimal("0"), total_amount - voucher.discount_amount)

            order.total_amount = total_amount
            order.save(update_fields=["total_amount"])
            created_orders += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded dashboard demo data: "
                f"{len(customers)} customers, {created_orders} orders, "
                f"{created_items} order items, {len(vouchers)} vouchers."
            )
        )