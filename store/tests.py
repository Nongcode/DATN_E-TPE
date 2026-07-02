from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .background_tasks import (
    RECURRING_DAILY_MARKER,
    RECURRING_MINUTES_PREFIX,
    hide_out_of_stock_products,
    run_due_scheduled_tasks,
    send_birthday_care_emails,
    send_low_stock_alerts,
)
from .models import CartItem, Category, Customer, Inventory, Product, ScheduledTask, Voucher
from .recommendations import get_similar_products


class ShoppingFlowTests(TestCase):
    def setUp(self):
        self.visible_category = Category.objects.create(
            name="Camera hành trình",
            slug="camera-hanh-trinh",
            status="visible",
        )
        self.hidden_category = Category.objects.create(
            name="Danh mục ẩn",
            slug="danh-muc-an",
            status="hidden",
        )
        self.product = Product.objects.create(
            category=self.visible_category,
            name="Camera ETEK A1",
            slug="camera-etek-a1",
            sku="ETEK-A1",
            description="Camera hành trình rõ nét.",
            price=1500000,
            is_active=True,
        )
        Product.objects.create(
            category=self.visible_category,
            name="Sản phẩm ngừng bán",
            slug="san-pham-ngung-ban",
            sku="ETEK-OFF",
            description="Không hiển thị.",
            price=100000,
            is_active=False,
        )
        Product.objects.create(
            category=self.hidden_category,
            name="Sản phẩm danh mục ẩn",
            slug="san-pham-danh-muc-an",
            sku="ETEK-HIDDEN",
            description="Không hiển thị.",
            price=100000,
            is_active=True,
        )

    def test_product_list_only_shows_active_products_in_visible_categories(self):
        response = self.client.get(reverse("store:product_list"))

        self.assertContains(response, self.product.name)
        self.assertNotContains(response, "Sản phẩm ngừng bán")
        self.assertNotContains(response, "Sản phẩm danh mục ẩn")

    def test_product_list_is_paginated_by_nine_products(self):
        for index in range(10):
            Product.objects.create(
                category=self.visible_category,
                name=f"Camera phân trang {index}",
                slug=f"camera-phan-trang-{index}",
                sku=f"PAGE-{index}",
                description="Sản phẩm kiểm tra phân trang.",
                price=100000 + index,
                is_active=True,
            )

        first_page = self.client.get(reverse("store:product_list"))
        second_page = self.client.get(reverse("store:product_list"), {"page": 2})

        self.assertEqual(len(first_page.context["products"]), 9)
        self.assertEqual(first_page.context["total_products"], 11)
        self.assertEqual(second_page.context["page_obj"].number, 2)
        self.assertEqual(len(second_page.context["products"]), 2)

    def test_smart_search_matches_unaccented_query(self):
        response = self.client.get(reverse("store:product_list"), {"q": "camera hanh trinh"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertEqual(response.context["search_context"]["tokens"], ["camera", "hanh", "trinh"])

    def test_smart_search_matches_description_and_category(self):
        sensor_category = Category.objects.create(
            name="Cảm biến ô tô",
            slug="cam-bien-o-to",
            status="visible",
            description="Thiết bị hỗ trợ an toàn khi lùi xe và chuyển làn.",
        )
        parking_sensor = Product.objects.create(
            category=sensor_category,
            name="Bộ hỗ trợ đỗ xe ETEK",
            slug="bo-ho-tro-do-xe-etek",
            sku="PARK-SAFE",
            description="Cảm biến lùi 4 mắt, âm báo khoảng cách, hỗ trợ quan sát điểm mù.",
            price=1800000,
            is_active=True,
        )

        response = self.client.get(reverse("store:product_list"), {"q": "diem mu"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, parking_sensor.name)

    def test_product_detail_shows_correct_product_data(self):
        response = self.client.get(reverse("store:product_detail", args=[self.product.pk]))

        self.assertContains(response, self.product.name)
        self.assertContains(response, self.product.sku)
        self.assertContains(response, "Camera hành trình rõ nét.")

    def test_content_based_recommendations_prioritize_similar_products(self):
        same_category_product = Product.objects.create(
            category=self.visible_category,
            name="Camera hành trình GPS ETEK A2",
            slug="camera-hanh-trinh-gps-etek-a2",
            sku="ETEK-A2",
            description="Camera hành trình GPS ghi hình rõ nét và cảnh báo va chạm.",
            price=1600000,
            is_active=True,
        )
        accessory_category = Category.objects.create(
            name="Dụng cụ sửa chữa Garage",
            slug="dung-cu-sua-chua-garage-test",
            status="visible",
        )
        Product.objects.create(
            category=accessory_category,
            name="Bộ kiểm tra ắc quy ETEK",
            slug="bo-kiem-tra-ac-quy-etek",
            sku="ETEK-BT",
            description="Dụng cụ kiểm tra điện áp ắc quy và máy phát.",
            price=900000,
            is_active=True,
        )

        similar_products = get_similar_products(
            self.product,
            Product.objects.filter(is_active=True).select_related("category"),
            limit=2,
        )

        self.assertIn(same_category_product, similar_products)
        self.assertEqual(similar_products[0], same_category_product)

    def test_product_detail_provides_similar_and_bundle_recommendations(self):
        Product.objects.create(
            category=self.visible_category,
            name="Camera hành trình mini ETEK",
            slug="camera-hanh-trinh-mini-etek",
            sku="ETEK-MINI",
            description="Camera hành trình nhỏ gọn, góc rộng.",
            price=1200000,
            is_active=True,
        )
        garage_category = Category.objects.create(
            name="Dụng cụ sửa chữa Garage",
            slug="dung-cu-sua-chua-garage-detail",
            status="visible",
        )
        bundle_product = Product.objects.create(
            category=garage_category,
            name="Máy chẩn đoán lỗi OBD2 ETEK",
            slug="may-chan-doan-loi-obd2-etek",
            sku="ETEK-OBD",
            description="Máy đọc lỗi OBD2 hỗ trợ kiểm tra hệ thống điện xe.",
            price=1300000,
            is_active=True,
        )

        response = self.client.get(reverse("store:product_detail", args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("similar_products", response.context)
        self.assertIn("bundle_products", response.context)
        self.assertContains(response, "Sản phẩm tương tự")
        self.assertContains(response, "Sản phẩm thường dùng cùng")
        self.assertIn(bundle_product, list(response.context["bundle_products"]))

    def test_add_to_cart_creates_session_cart_and_increments_quantity(self):
        add_url = reverse("store:add_to_cart", args=[self.product.pk])

        self.client.post(add_url, {"quantity": "2"})
        self.client.post(add_url, {"quantity": "3"})

        item = CartItem.objects.get(product=self.product)
        self.assertEqual(item.quantity, 5)
        response = self.client.get(reverse("store:cart_detail"))
        self.assertContains(response, "5 sản phẩm")
        self.assertContains(response, "7,500,000 đ")

    def test_add_to_cart_ajax_returns_json_summary(self):
        response = self.client.post(
            reverse("store:add_to_cart", args=[self.product.pk]),
            {"quantity": "2"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["cart_item_count"], 2)
        self.assertIn(self.product.name, data["message"])

    def test_cart_item_quantity_can_be_updated_and_removed(self):
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "2"})
        item = CartItem.objects.get(product=self.product)

        self.client.post(reverse("store:update_cart_item", args=[item.pk]), {"action": "increase"})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 3)

        self.client.post(
            reverse("store:update_cart_item", args=[item.pk]),
            {"action": "set", "quantity": "7"},
        )
        item.refresh_from_db()
        self.assertEqual(item.quantity, 7)

        self.client.post(reverse("store:remove_cart_item", args=[item.pk]))
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_contact_page_renders_and_accepts_request(self):
        response = self.client.get(reverse("store:contact"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gửi yêu cầu tư vấn")

        post_response = self.client.post(
            reverse("store:contact"),
            {"name": "Anh Long", "phone": "0900000000", "message": "Cần tư vấn camera."},
        )
        self.assertRedirects(post_response, reverse("store:contact"))

    def test_news_cards_link_to_detail_page(self):
        list_response = self.client.get(reverse("store:news_list"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, reverse("store:news_detail", args=["fallback-1"]))

        detail_response = self.client.get(reverse("store:news_detail", args=["fallback-1"]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Quay lại xem tin tức")
        self.assertContains(detail_response, "Bài viết tương tự")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="ETEK Test <test@etek.local>",
    STOCK_ALERT_EMAILS=["stock@etek.local"],
    BIRTHDAY_VOUCHER_AMOUNT="150000",
    BIRTHDAY_VOUCHER_VALID_DAYS=2,
)
class BackgroundTaskTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.category = Category.objects.create(
            name="Dụng cụ sửa chữa Garage",
            slug="dung-cu-sua-chua-garage-bg",
            status="visible",
        )
        self.low_stock_product = Product.objects.create(
            category=self.category,
            name="Máy chẩn đoán lỗi OBD2 ETEK",
            slug="may-chan-doan-loi-obd2-bg",
            sku="BG-OBD",
            description="Máy đọc lỗi OBD2 phục vụ garage.",
            price=1300000,
            is_active=True,
        )
        self.out_of_stock_product = Product.objects.create(
            category=self.category,
            name="Bộ kiểm tra ắc quy ETEK",
            slug="bo-kiem-tra-ac-quy-bg",
            sku="BG-BT",
            description="Dụng cụ kiểm tra ắc quy.",
            price=900000,
            is_active=True,
        )
        self.safe_product = Product.objects.create(
            category=self.category,
            name="Bộ khẩu tay vặn ETEK",
            slug="bo-khau-tay-van-bg",
            sku="BG-SAFE",
            description="Bộ khẩu sửa chữa.",
            price=800000,
            is_active=True,
        )
        Inventory.objects.create(product=self.low_stock_product, quantity=2, low_stock_threshold=5)
        Inventory.objects.create(product=self.out_of_stock_product, quantity=0, low_stock_threshold=5)
        Inventory.objects.create(product=self.safe_product, quantity=12, low_stock_threshold=5)

    def create_customer(self, username, email, date_of_birth):
        user = User.objects.create_user(username=username, email=email)
        return Customer.objects.create(
            user=user,
            full_name=f"Khách {username}",
            email=email,
            phone_number="0900000000",
            address="Hà Nội",
            date_of_birth=date_of_birth,
        )

    def test_low_stock_alert_sends_email_only_for_positive_low_quantity(self):
        result = send_low_stock_alerts()

        self.assertEqual(result.processed, 1)
        self.assertEqual(result.sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.low_stock_product.name, mail.outbox[0].body)
        self.assertNotIn(self.out_of_stock_product.name, mail.outbox[0].body)
        self.assertNotIn(self.safe_product.name, mail.outbox[0].body)

    def test_low_stock_alert_with_no_matching_inventory_does_not_send_email(self):
        self.low_stock_product.inventory.quantity = 8
        self.low_stock_product.inventory.save(update_fields=["quantity"])

        result = send_low_stock_alerts()

        self.assertEqual(result.processed, 0)
        self.assertEqual(result.sent, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_low_stock_alert_dry_run_does_not_send_email(self):
        result = send_low_stock_alerts(dry_run=True)

        self.assertEqual(result.processed, 1)
        self.assertEqual(result.sent, 0)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(STOCK_ALERT_EMAILS=[])
    def test_low_stock_alert_falls_back_to_staff_email(self):
        User.objects.create_user(username="staff", email="admin@etek.local", is_staff=True)

        result = send_low_stock_alerts()

        self.assertEqual(result.sent, 1)
        self.assertEqual(mail.outbox[0].to, ["admin@etek.local"])

    def test_auto_hide_out_of_stock_products_only_hides_zero_quantity(self):
        result = hide_out_of_stock_products()

        self.low_stock_product.refresh_from_db()
        self.out_of_stock_product.refresh_from_db()
        self.safe_product.refresh_from_db()
        self.assertEqual(result.updated, 1)
        self.assertTrue(self.low_stock_product.is_active)
        self.assertFalse(self.out_of_stock_product.is_active)
        self.assertTrue(self.safe_product.is_active)

    def test_auto_hide_dry_run_does_not_change_products(self):
        result = hide_out_of_stock_products(dry_run=True)

        self.out_of_stock_product.refresh_from_db()
        self.assertEqual(result.processed, 1)
        self.assertEqual(result.updated, 0)
        self.assertTrue(self.out_of_stock_product.is_active)

    def test_birthday_task_creates_voucher_and_sends_care_email(self):
        today = timezone.localdate()
        customer = self.create_customer("birthday", "birthday@etek.local", today)

        result = send_birthday_care_emails(today=today)

        voucher = Voucher.objects.get(customer=customer)
        self.assertEqual(result.processed, 1)
        self.assertEqual(result.sent, 1)
        self.assertEqual(voucher.discount_amount, 150000)
        self.assertIn(voucher.code, mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, [customer.email])

    def test_birthday_task_ignores_customers_without_valid_birthday_email(self):
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        self.create_customer("noemail", None, today)
        self.create_customer("wrongday", "wrongday@etek.local", tomorrow)

        result = send_birthday_care_emails(today=today)

        self.assertEqual(result.processed, 0)
        self.assertEqual(result.sent, 0)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_birthday_task_is_idempotent_for_same_day(self):
        today = timezone.localdate()
        customer = self.create_customer("duplicate", "duplicate@etek.local", today)

        first_result = send_birthday_care_emails(today=today)
        second_result = send_birthday_care_emails(today=today)

        self.assertEqual(first_result.sent, 1)
        self.assertEqual(second_result.sent, 0)
        self.assertEqual(second_result.skipped, 1)
        self.assertEqual(Voucher.objects.filter(customer=customer).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_due_scheduled_task_runs_and_updates_status(self):
        task = ScheduledTask.objects.create(
            task_type="lock_stock",
            run_at=timezone.now() - timedelta(minutes=1),
        )

        results = run_due_scheduled_tasks()

        task.refresh_from_db()
        self.assertEqual(len(results), 1)
        self.assertEqual(task.status, "success")
        self.assertIn("low_stock_alert", task.execution_log)

    def test_recurring_daily_scheduled_task_reschedules_next_run(self):
        due_time = timezone.now() - timedelta(minutes=1)
        task = ScheduledTask.objects.create(
            task_type="lock_stock",
            status="pending",
            run_at=due_time,
            execution_log=f"{RECURRING_DAILY_MARKER}; default_task=true",
        )

        results = run_due_scheduled_tasks(now=timezone.now())

        task.refresh_from_db()
        self.assertEqual(len(results), 1)
        self.assertEqual(task.status, "pending")
        self.assertGreater(task.run_at, timezone.now())
        self.assertIn(RECURRING_DAILY_MARKER, task.execution_log)
        self.assertIn("next_run_at=", task.execution_log)
        self.assertIn("low_stock_alert", task.execution_log)

    def test_recurring_interval_scheduled_task_reschedules_by_minutes(self):
        now = timezone.now()
        task = ScheduledTask.objects.create(
            task_type="auto_hide",
            status="pending",
            run_at=now - timedelta(minutes=1),
            execution_log=f"{RECURRING_MINUTES_PREFIX}5; default_task=true",
        )

        results = run_due_scheduled_tasks(now=now)

        task.refresh_from_db()
        self.assertEqual(len(results), 1)
        self.assertEqual(task.status, "pending")
        self.assertGreater(task.run_at, now)
        self.assertLessEqual(task.run_at, now + timedelta(minutes=5))
        self.assertIn(f"{RECURRING_MINUTES_PREFIX}5", task.execution_log)
        self.assertIn("auto_hide_out_of_stock", task.execution_log)

    def test_due_scheduled_task_ignores_future_task(self):
        task = ScheduledTask.objects.create(
            task_type="auto_hide",
            run_at=timezone.now() + timedelta(hours=1),
        )

        results = run_due_scheduled_tasks()

        task.refresh_from_db()
        self.assertEqual(results, [])
        self.assertEqual(task.status, "pending")
        self.assertEqual(task.execution_log, None)

    def test_due_scheduled_task_marks_unknown_type_as_failed(self):
        task = ScheduledTask.objects.create(
            task_type="unknown",
            run_at=timezone.now() - timedelta(minutes=1),
        )

        results = run_due_scheduled_tasks()

        task.refresh_from_db()
        self.assertEqual(len(results), 1)
        self.assertEqual(task.status, "failed")
        self.assertIn("Unsupported scheduled task type", task.execution_log)

    def test_management_command_dry_run_does_not_hide_products(self):
        call_command("run_scheduled_tasks", task="auto-hide", dry_run=True)

        self.out_of_stock_product.refresh_from_db()
        self.assertTrue(self.out_of_stock_product.is_active)

    def test_management_command_default_runs_due_scheduled_tasks(self):
        task = ScheduledTask.objects.create(
            task_type="auto_hide",
            run_at=timezone.now() - timedelta(minutes=1),
        )

        call_command("run_scheduled_tasks")

        task.refresh_from_db()
        self.out_of_stock_product.refresh_from_db()
        self.assertEqual(task.status, "success")
        self.assertFalse(self.out_of_stock_product.is_active)

    def test_seed_default_scheduled_tasks_command_creates_three_pending_tasks_once(self):
        call_command("seed_default_scheduled_tasks")
        call_command("seed_default_scheduled_tasks")

        pending_tasks = ScheduledTask.objects.filter(status="pending").order_by("task_type")
        self.assertEqual(pending_tasks.count(), 3)
        self.assertEqual(
            set(pending_tasks.values_list("task_type", flat=True)),
            {"auto_hide", "birthday_mail", "lock_stock"},
        )
        task_markers = {task.task_type: task.execution_log for task in pending_tasks}
        self.assertIn(f"{RECURRING_MINUTES_PREFIX}5", task_markers["auto_hide"])
        self.assertIn(f"{RECURRING_MINUTES_PREFIX}360", task_markers["lock_stock"])
        self.assertIn(RECURRING_DAILY_MARKER, task_markers["birthday_mail"])
        for task in pending_tasks:
            self.assertGreater(task.run_at, timezone.now())




