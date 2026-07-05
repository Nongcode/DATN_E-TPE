from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core import mail
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .admin import CategoryAdmin, ProductAdmin
from .background_tasks import (
    RECURRING_DAILY_MARKER,
    RECURRING_MINUTES_PREFIX,
    hide_out_of_stock_products,
    run_due_scheduled_tasks,
    send_birthday_care_emails,
    send_low_stock_alerts,
)
from .models import CartItem, Category, ConsultationRequest, Customer, Inventory, Order, Product, ScheduledTask, Voucher
from .recommendations import get_bundle_products, get_similar_products


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

    def test_recommendations_prioritize_vehicle_compatibility(self):
        self.product.compatible_car_brands = "Toyota"
        self.product.compatible_car_models = "Vios"
        self.product.save(update_fields=["compatible_car_brands", "compatible_car_models"])

        garage_category = Category.objects.create(
            name="Dụng cụ sửa chữa Garage",
            slug="dung-cu-sua-chua-garage-vehicle",
            status="visible",
        )
        compatible_product = Product.objects.create(
            category=garage_category,
            name="Bộ cảm biến áp suất lốp cho Toyota Vios",
            slug="bo-cam-bien-ap-suat-lop-toyota-vios",
            sku="TPMS-VIOS",
            description="Phụ kiện theo dõi áp suất lốp cho xe Toyota Vios.",
            compatible_car_brands="Toyota",
            compatible_car_models="Vios",
            price=1800000,
            is_active=True,
        )
        Product.objects.create(
            category=self.visible_category,
            name="Camera hành trình phổ thông",
            slug="camera-hanh-trinh-pho-thong",
            sku="CAM-GENERIC",
            description="Camera hành trình dùng chung cho nhiều xe.",
            price=1450000,
            is_active=True,
        )

        similar_products = get_similar_products(
            self.product,
            Product.objects.filter(is_active=True).select_related("category"),
            limit=2,
        )

        self.assertEqual(similar_products[0], compatible_product)

    def test_recommendations_use_brand_and_manufacturer_metadata(self):
        self.product.brand = "CORGHI"
        self.product.manufacturer = "Corghi S.p.A"
        self.product.save(update_fields=["brand", "manufacturer"])

        garage_category = Category.objects.create(
            name="Thiết bị lốp & nâng hạ",
            slug="thiet-bi-lop-nang-ha-brand-test",
            status="visible",
        )
        same_brand_product = Product.objects.create(
            category=garage_category,
            name="Máy ra vào lốp CORGHI A2024",
            slug="may-ra-vao-lop-corghi-a2024",
            sku="CORGHI-A2024",
            description="Thiết bị garage chính hãng cho lốp ô tô.",
            brand="CORGHI",
            manufacturer="Corghi S.p.A",
            price=52000000,
            is_active=True,
        )
        Product.objects.create(
            category=garage_category,
            name="Máy ra vào lốp thương hiệu khác",
            slug="may-ra-vao-lop-thuong-hieu-khac",
            sku="OTHER-TIRE",
            description="Thiết bị garage cùng phân khúc nhưng khác thương hiệu.",
            brand="OTHER",
            manufacturer="Other Factory",
            price=50000000,
            is_active=True,
        )

        similar_products = get_similar_products(
            self.product,
            Product.objects.filter(is_active=True).select_related("category"),
            limit=2,
        )

        self.assertEqual(similar_products[0], same_brand_product)

    def test_bundle_recommendations_prioritize_complementary_use_case(self):
        source_category = Category.objects.create(
            name="Thiet bi lop nang ha",
            slug="thiet-bi-lop-nang-ha-bundle-source",
            status="visible",
        )
        source_product = Product.objects.create(
            category=source_category,
            name="May ra vao lop xe con tu dong",
            slug="may-ra-vao-lop-xe-con-tu-dong",
            sku="TIRE-MACHINE-01",
            description="Thiet bi lop dung trong garage de thao lap banh xe.",
            compatible_car_brands="Toyota",
            compatible_car_models="Vios",
            price=52000000,
            is_active=True,
        )
        garage_category = Category.objects.create(
            name="Dung cu sua chua Garage",
            slug="dung-cu-sua-chua-garage-bundle-use-case",
            status="visible",
        )
        complementary_product = Product.objects.create(
            category=garage_category,
            name="Sung van oc 1/2 inch cho garage lop",
            slug="sung-van-oc-garage-lop",
            sku="IMPACT-WRENCH-01",
            description="Dung cu hoi ho tro thao oc banh xe khi lam lop.",
            compatible_car_brands="Toyota",
            compatible_car_models="Vios",
            price=2350000,
            is_active=True,
        )
        Product.objects.create(
            category=source_category,
            name="May can bang lop xe con cung phan khuc",
            slug="may-can-bang-lop-cung-phan-khuc",
            sku="TIRE-BALANCER-01",
            description="Thiet bi lop lon cung phan khuc, khong phai phu kien mua kem truc tiep.",
            compatible_car_brands="Toyota",
            compatible_car_models="Vios",
            price=49000000,
            is_active=True,
        )

        bundle_products = get_bundle_products(
            source_product,
            Product.objects.filter(is_active=True).select_related("category"),
            limit=2,
        )

        self.assertEqual(bundle_products[0], complementary_product)

    def test_tire_machine_bundle_ignores_detailing_and_battery_products(self):
        source_category = Category.objects.create(
            name="Thiet bi lop nang ha",
            slug="thiet-bi-lop-nang-ha-strict-bundle-source",
            status="visible",
        )
        source_product = Product.objects.create(
            category=source_category,
            name="May can bang lop xe con",
            slug="may-can-bang-lop-xe-con-strict",
            sku="TIRE-BALANCER-STRICT",
            description="May can bang lop co thong so duong kinh lazang va kich thuoc chan may.",
            price=52000000,
            is_active=True,
        )
        garage_category = Category.objects.create(
            name="Dung cu sua chua Garage",
            slug="dung-cu-sua-chua-garage-strict-bundle",
            status="visible",
        )
        tire_tool = Product.objects.create(
            category=garage_category,
            name="Sung bom lop 90 PSI hien thi so",
            slug="sung-bom-lop-90-psi-hien-thi-so-strict",
            sku="AIR-GUN-STRICT",
            description="Dung cu bom lop truc tiep cho garage.",
            price=1800000,
            is_active=True,
        )
        battery_product = Product.objects.create(
            category=garage_category,
            name="May sac va khoi dong ac quy",
            slug="may-sac-va-khoi-dong-ac-quy-strict",
            sku="BATTERY-STRICT",
            description="May sac co thong so kich thuoc chan may va khi hau bao quan.",
            price=2500000,
            is_active=True,
        )
        detailing_category = Category.objects.create(
            name="Rua xe Detailing Dong son",
            slug="rua-xe-detailing-dong-son-strict-bundle",
            status="visible",
        )
        detailing_product = Product.objects.create(
            category=detailing_category,
            name="Hoa chat ve sinh lazang",
            slug="hoa-chat-ve-sinh-lazang-strict",
            sku="DETAILING-STRICT",
            description="Dung dich ve sinh lazang va be mat son.",
            price=1200000,
            is_active=True,
        )

        bundle_products = get_bundle_products(
            source_product,
            Product.objects.filter(is_active=True).select_related("category"),
            limit=4,
        )

        self.assertIn(tire_tool, bundle_products)
        self.assertNotIn(battery_product, bundle_products)
        self.assertNotIn(detailing_product, bundle_products)

    def test_bundle_recommendations_ignore_products_without_bundle_signal(self):
        source_category = Category.objects.create(
            name="Camera hanh trinh",
            slug="camera-hanh-trinh-bundle-source",
            status="visible",
        )
        source_product = Product.objects.create(
            category=source_category,
            name="Camera hanh trinh co giam sat dien ap",
            slug="camera-hanh-trinh-giam-sat-dien-ap",
            sku="CAM-BUNDLE-SOURCE",
            description="Camera hanh trinh ho tro theo doi he thong dien xe.",
            price=1800000,
            is_active=True,
        )
        unrelated_category = Category.objects.create(
            name="Tu dung cu luu tru",
            slug="tu-dung-cu-luu-tru-unrelated-bundle",
            status="visible",
        )
        unrelated_product = Product.objects.create(
            category=unrelated_category,
            name="Ke trung bay san pham showroom",
            slug="ke-trung-bay-san-pham-showroom",
            sku="DISPLAY-SHELF-01",
            description="Ke trung bay showroom doc lap.",
            price=3500000,
            is_active=True,
        )

        bundle_products = get_bundle_products(
            source_product,
            Product.objects.filter(is_active=True).select_related("category"),
            limit=4,
        )

        self.assertNotIn(unrelated_product, bundle_products)

    def test_product_detail_provides_similar_and_bundle_recommendations(self):
        for index in range(6):
            Product.objects.create(
                category=self.visible_category,
                name=f"Camera hanh trinh goi y {index}",
                slug=f"camera-hanh-trinh-goi-y-{index}",
                sku=f"ETEK-SIM-{index}",
                description="Camera hanh trinh nho gon, goc rong va ghi hinh ro net.",
                price=1200000 + index,
                is_active=True,
            )
        garage_category = Category.objects.create(
            name="Dung cu sua chua Garage",
            slug="dung-cu-sua-chua-garage-detail",
            status="visible",
        )
        bundle_product = Product.objects.create(
            category=garage_category,
            name="May chan doan loi OBD2 ETEK",
            slug="may-chan-doan-loi-obd2-etek",
            sku="ETEK-OBD",
            description="May doc loi OBD2 ho tro kiem tra he thong dien xe.",
            price=1300000,
            is_active=True,
        )

        response = self.client.get(reverse("store:product_detail", args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("similar_products", response.context)
        self.assertIn("bundle_products", response.context)
        self.assertEqual(len(response.context["similar_products"]), 6)
        self.assertContains(response, "Sản phẩm tương tự")
        self.assertContains(response, "Sản phẩm thường dùng cùng")
        self.assertContains(response, 'data-recommendation-next="similar"')
        self.assertContains(response, 'data-recommendation-next="bundle"')
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

    def test_auth_pages_render(self):
        login_response = self.client.get(reverse("store:login"))
        register_response = self.client.get(reverse("store:register"))

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(register_response.status_code, 200)
        self.assertContains(login_response, "auth-form")
        self.assertContains(register_response, "auth-form")

    def test_register_help_text_shows_only_after_invalid_submit(self):
        response = self.client.get(reverse("store:register"))

        self.assertNotContains(response, "Y\u00eau c\u1ea7u.")
        self.assertNotContains(response, "M\u1eadt kh\u1ea9u kh\u00f4ng \u0111\u01b0\u1ee3c qu\u00e1 gi\u1ed1ng")

        invalid_response = self.client.post(
            reverse("store:register"),
            {
                "username": "newcustomer",
                "full_name": "Anh Long",
                "phone_number": "0889584291",
                "email": "invalid@example.com",
                "date_of_birth": "1998-05-20",
                "address": "Ha Noi",
                "password1": "123",
                "password2": "456",
            },
        )

        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, "Y\u00eau c\u1ea7u.")
        self.assertContains(invalid_response, "M\u1eadt kh\u1ea9u kh\u00f4ng \u0111\u01b0\u1ee3c qu\u00e1 gi\u1ed1ng")
        self.assertContains(invalid_response, "Hai m\u1eadt kh\u1ea9u x\u00e1c nh\u1eadn kh\u00f4ng kh\u1edbp.")
        self.assertContains(invalid_response, "has-error")

        short_password_response = self.client.post(
            reverse("store:register"),
            {
                "username": "shortpasswordcustomer",
                "full_name": "Anh Long",
                "phone_number": "0889584292",
                "email": "short@example.com",
                "date_of_birth": "1998-05-20",
                "address": "Ha Noi",
                "password1": "123",
                "password2": "123",
            },
        )

        self.assertContains(short_password_response, "M\u1eadt kh\u1ea9u qu\u00e1 ng\u1eafn.")
        self.assertNotContains(short_password_response, "This password is too short")

    def test_register_rejects_future_birth_date(self):
        response = self.client.post(
            reverse("store:register"),
            {
                "username": "futurebirthday",
                "full_name": "Anh Long",
                "phone_number": "0889584293",
                "email": "future@example.com",
                "date_of_birth": "2999-01-01",
                "address": "Ha Noi",
                "password1": "S3cureDemoPass!2026",
                "password2": "S3cureDemoPass!2026",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ng\u00e0y sinh kh\u00f4ng \u0111\u01b0\u1ee3c l\u1edbn h\u01a1n ng\u00e0y hi\u1ec7n t\u1ea1i.")
        self.assertFalse(User.objects.filter(username="futurebirthday").exists())

    def test_register_rejects_duplicate_email_and_phone_number(self):
        existing_user = User.objects.create_user(
            username="existingcustomer",
            email="used@example.com",
            password="S3cureDemoPass!2026",
        )
        Customer.objects.create(
            user=existing_user,
            full_name="Existing Customer",
            email="used@example.com",
            phone_number="0889584999",
            address="Ha Noi",
            date_of_birth="1990-01-01",
        )

        duplicate_email_response = self.client.post(
            reverse("store:register"),
            {
                "username": "duplicateemail",
                "full_name": "Anh Email",
                "phone_number": "0889584001",
                "email": "used@example.com",
                "date_of_birth": "1998-05-20",
                "address": "Ha Noi",
                "password1": "S3cureDemoPass!2026",
                "password2": "S3cureDemoPass!2026",
            },
        )
        self.assertEqual(duplicate_email_response.status_code, 200)
        self.assertContains(duplicate_email_response, "Email n\u00e0y \u0111\u00e3 \u0111\u01b0\u1ee3c s\u1eed d\u1ee5ng.")
        self.assertFalse(User.objects.filter(username="duplicateemail").exists())

        duplicate_phone_response = self.client.post(
            reverse("store:register"),
            {
                "username": "duplicatephone",
                "full_name": "Anh Phone",
                "phone_number": "0889584999",
                "email": "newphone@example.com",
                "date_of_birth": "1998-05-20",
                "address": "Ha Noi",
                "password1": "S3cureDemoPass!2026",
                "password2": "S3cureDemoPass!2026",
            },
        )
        self.assertEqual(duplicate_phone_response.status_code, 200)
        self.assertContains(duplicate_phone_response, "S\u1ed1 \u0111i\u1ec7n tho\u1ea1i n\u00e0y \u0111\u00e3 \u0111\u01b0\u1ee3c s\u1eed d\u1ee5ng.")
        self.assertFalse(User.objects.filter(username="duplicatephone").exists())

    def test_register_creates_customer_profile_and_prefills_contact_form(self):
        response = self.client.post(
            reverse("store:register"),
            {
                "username": "newcustomer",
                "full_name": "Anh Long",
                "phone_number": "0889584290",
                "email": "long@example.com",
                "date_of_birth": "1998-05-20",
                "address": "Cau Giay, Ha Noi",
                "password1": "S3cureDemoPass!2026",
                "password2": "S3cureDemoPass!2026",
                "next": reverse("store:contact"),
            },
        )

        self.assertRedirects(response, reverse("store:contact"))
        user = User.objects.get(username="newcustomer")
        profile = user.customer_profile
        self.assertEqual(profile.full_name, "Anh Long")
        self.assertEqual(profile.phone_number, "0889584290")
        self.assertEqual(profile.email, "long@example.com")
        self.assertEqual(profile.date_of_birth.isoformat(), "1998-05-20")

        contact_response = self.client.get(reverse("store:contact"))
        self.assertContains(contact_response, 'value="Anh Long"')
        self.assertContains(contact_response, 'value="0889584290"')
        self.assertContains(contact_response, 'value="long@example.com"')

    def test_login_prefills_contact_form_from_customer_profile(self):
        user = User.objects.create_user(
            username="profilecustomer",
            password="S3cureDemoPass!2026",
            email="profile@example.com",
        )
        Customer.objects.create(
            user=user,
            full_name="Chi Thao",
            email="profile@example.com",
            phone_number="0901234567",
            address="Ha Noi",
        )

        response = self.client.post(
            reverse("store:login"),
            {
                "username": "profilecustomer",
                "password": "S3cureDemoPass!2026",
                "next": reverse("store:contact"),
            },
        )

        self.assertRedirects(response, reverse("store:contact"))
        contact_response = self.client.get(reverse("store:contact"))
        self.assertContains(contact_response, 'value="Chi Thao"')
        self.assertContains(contact_response, 'value="0901234567"')
        self.assertContains(contact_response, 'value="profile@example.com"')

    def test_cart_contact_prefills_products_without_reselecting(self):
        accessory = Product.objects.create(
            category=self.visible_category,
            name="Camera hanh trinh goi y lien he",
            slug="camera-hanh-trinh-goi-y-lien-he",
            sku="CONTACT-CAM-1",
            description="San pham dung de kiem tra lien he tu gio hang.",
            price=900000,
            is_active=True,
        )
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "2"})
        self.client.post(reverse("store:add_to_cart", args=[accessory.pk]), {"quantity": "1"})

        cart_response = self.client.get(reverse("store:cart_detail"))
        self.assertContains(cart_response, reverse("store:login"))
        self.assertContains(cart_response, "next=/lien-he/%3Ffrom%3Dcart")

        user = User.objects.create_user(username="cartcontact", password="S3cureDemoPass!2026")
        self.client.force_login(user)
        response = self.client.get(f'{reverse("store:contact")}?from=cart')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["use_cart_products"])
        self.assertEqual(len(response.context["cart_contact_items"]), 2)
        self.assertContains(response, "Sản phẩm đã đính kèm từ giỏ hàng")
        self.assertContains(response, self.product.name)
        self.assertContains(response, accessory.name)
        self.assertContains(response, f'name="product_ids" value="{self.product.pk}"')
        self.assertContains(response, f'name="product_ids" value="{accessory.pk}"')
        self.assertContains(response, 'name="source" value="cart"')
        self.assertContains(response, "Số lượng: 2")
        self.assertNotContains(response, 'type="checkbox" name="product_ids"')

        post_response = self.client.post(
            reverse("store:contact"),
            {
                "name": "Anh Long",
                "phone": "0900000000",
                "source": "cart",
                "product_ids": [str(self.product.pk), str(accessory.pk)],
            },
        )

        self.assertRedirects(post_response, reverse("store:contact"))
        consultation_request = ConsultationRequest.objects.get()
        self.assertEqual(consultation_request.status, "pending")
        self.assertEqual(consultation_request.customer.user, user)
        self.assertEqual(consultation_request.phone, "0900000000")
        self.assertEqual(consultation_request.items.count(), 2)
        item_quantities = {
            item.product_id: item.quantity
            for item in consultation_request.items.select_related("product")
        }
        self.assertEqual(item_quantities[self.product.pk], 2)
        self.assertEqual(item_quantities[accessory.pk], 1)
        self.assertEqual(Order.objects.count(), 0)

        feedback = [str(message) for message in get_messages(post_response.wsgi_request)]
        self.assertTrue(any("Yêu cầu tư vấn của bạn đã được gửi thành công" in message for message in feedback))

    def test_order_status_choices_follow_fulfillment_flow(self):
        choices = [value for value, _label in Order.STATUS_CHOICES]

        self.assertEqual(choices, ["Pending", "Confirmed", "Shipping", "Shipped", "Cancelled"])

    def test_pending_order_can_be_cancelled_before_confirmation(self):
        user = User.objects.create_user(username="pendingcancel")
        customer = Customer.objects.create(
            user=user,
            full_name="Pending Cancel",
            phone_number="0889000001",
            address="Ha Noi",
            date_of_birth="1998-05-20",
        )
        order = Order.objects.create(customer=customer, total_amount=1000, status="Pending")

        order.status = "Cancelled"
        order.save(update_fields=["status"])

        order.refresh_from_db()
        self.assertEqual(order.status, "Cancelled")

    def test_confirmed_order_cannot_be_cancelled(self):
        user = User.objects.create_user(username="confirmedcancel")
        customer = Customer.objects.create(
            user=user,
            full_name="Confirmed Cancel",
            phone_number="0889000002",
            address="Ha Noi",
            date_of_birth="1998-05-20",
        )
        order = Order.objects.create(customer=customer, total_amount=1000, status="Pending")
        order.status = "Confirmed"
        order.save(update_fields=["status"])

        order.status = "Cancelled"
        with self.assertRaisesMessage(ValidationError, "Đơn hàng đã lên đơn nên không thể hủy."):
            order.save(update_fields=["status"])

        order.refresh_from_db()
        self.assertEqual(order.status, "Confirmed")

    def test_cart_order_creates_order_and_decreases_inventory(self):
        accessory = Product.objects.create(
            category=self.visible_category,
            name="Camera hanh trinh dat hang kem",
            slug="camera-hanh-trinh-dat-hang-kem",
            sku="ORDER-CAM-1",
            description="San pham dung de kiem tra dat hang tu gio hang.",
            price=900000,
            is_active=True,
        )
        Inventory.objects.create(product=self.product, quantity=5, low_stock_threshold=20)
        Inventory.objects.create(product=accessory, quantity=3, low_stock_threshold=20)

        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "2"})
        self.client.post(reverse("store:add_to_cart", args=[accessory.pk]), {"quantity": "1"})

        user = User.objects.create_user(username="cartorder", password="S3cureDemoPass!2026")
        self.client.force_login(user)
        response = self.client.post(
            f'{reverse("store:contact")}?from=cart',
            {
                "name": "Anh Long",
                "phone": "0900000000",
                "source": "cart",
                "request_type": "order",
                "product_ids": [str(self.product.pk), str(accessory.pk)],
            },
        )

        self.assertRedirects(response, reverse("store:contact"))
        order = Order.objects.get()
        self.assertEqual(order.status, "Pending")
        self.assertEqual(order.customer.user, user)
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.total_amount, self.product.price * 2 + accessory.price)

        self.product.inventory.refresh_from_db()
        accessory.inventory.refresh_from_db()
        self.assertEqual(self.product.inventory.quantity, 3)
        self.assertEqual(accessory.inventory.quantity, 2)
        self.assertFalse(CartItem.objects.filter(cart__user=user).exists())

        feedback = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(any("B\u1ea1n \u0111\u00e3 \u0111\u1eb7t h\u00e0ng th\u00e0nh c\u00f4ng" in message and f"#{order.id}" in message for message in feedback))

    def test_cart_order_does_not_create_order_when_stock_is_insufficient(self):
        Inventory.objects.create(product=self.product, quantity=1, low_stock_threshold=20)
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "2"})

        user = User.objects.create_user(username="lowstockorder", password="S3cureDemoPass!2026")
        self.client.force_login(user)
        response = self.client.post(
            f'{reverse("store:contact")}?from=cart',
            {
                "name": "Anh Long",
                "phone": "0900000000",
                "source": "cart",
                "request_type": "order",
                "product_ids": [str(self.product.pk)],
            },
        )

        self.assertRedirects(response, f'{reverse("store:contact")}?from=cart')
        self.assertEqual(Order.objects.count(), 0)
        self.product.inventory.refresh_from_db()
        self.assertEqual(self.product.inventory.quantity, 1)
        feedback = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(any("kh\u00f4ng \u0111\u1ee7 t\u1ed3n kho" in message for message in feedback))

    def test_contact_page_requires_login_before_submit(self):
        response = self.client.get(reverse("store:contact"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "contact-auth-required")
        self.assertContains(response, reverse("store:login"))

        post_response = self.client.post(
            reverse("store:contact"),
            {"name": "Anh Long", "phone": "0900000000", "message": "Can tu van camera."},
        )
        self.assertRedirects(
            post_response,
            f'{reverse("store:login")}?next=%2Flien-he%2F',
            fetch_redirect_response=False,
        )

        user = User.objects.create_user(username="contactuser", password="S3cureDemoPass!2026")
        self.client.force_login(user)
        authenticated_response = self.client.get(reverse("store:contact"))
        self.assertContains(authenticated_response, "contact-form")
        self.assertNotContains(authenticated_response, "contact-auth-required")

        accepted_response = self.client.post(
            reverse("store:contact"),
            {"name": "Anh Long", "phone": "0900000000", "message": "Can tu van camera."},
        )
        self.assertRedirects(accepted_response, reverse("store:contact"))
        consultation_request = ConsultationRequest.objects.get()
        self.assertEqual(consultation_request.name, "Anh Long")
        self.assertEqual(consultation_request.message, "Can tu van camera.")
        self.assertEqual(consultation_request.status, "pending")

    def test_news_cards_link_to_detail_page(self):
        list_response = self.client.get(reverse("store:news_list"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, reverse("store:news_detail", args=["fallback-1"]))

        detail_response = self.client.get(reverse("store:news_detail", args=["fallback-1"]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Quay lại xem tin tức")
        self.assertContains(detail_response, "Bài viết tương tự")


class AdminImportExportTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Import Export Category",
            slug="import-export-category",
            status="visible",
        )
        self.product = Product.objects.create(
            category=self.category,
            name="Import Export Product",
            slug="import-export-product",
            sku="IMPORT-EXPORT-PRODUCT",
            description="Product used to verify admin import/export.",
            price=1230000,
            is_active=True,
        )
        self.request = RequestFactory().get("/admin/")
        self.request.user = User(username="admin", is_staff=True, is_superuser=True)

    def test_product_and_category_admin_export_import_dry_run(self):
        product_admin = ProductAdmin(Product, admin.site)
        product_resource = product_admin.get_resource_classes(self.request)[0]()
        product_export = product_resource.export(Product.objects.filter(pk=self.product.pk))

        self.assertEqual(product_export.height, 1)
        self.assertIn("sku", product_export.headers)
        self.assertIn("price", product_export.headers)

        product_dataset = product_resource.export(Product.objects.none())
        values = {
            "id": "",
            "category": str(self.category.pk),
            "name": "Imported Product Dry Run",
            "slug": "imported-product-dry-run",
            "sku": "IMPORTED-DRY-RUN",
            "description": "Dry-run import product.",
            "price": "990000.00",
            "is_active": "1",
        }
        product_dataset.append([values.get(header, "") for header in product_dataset.headers])
        product_result = product_resource.import_data(product_dataset, dry_run=True, raise_errors=False)

        self.assertFalse(product_result.has_errors())
        self.assertFalse(Product.objects.filter(sku="IMPORTED-DRY-RUN").exists())

        category_admin = CategoryAdmin(Category, admin.site)
        category_resource = category_admin.get_resource_classes(self.request)[0]()
        category_dataset = category_resource.export(Category.objects.none())
        category_values = {
            "id": "",
            "name": "Imported Category Dry Run",
            "slug": "imported-category-dry-run",
            "status": "visible",
            "description": "Dry-run import category.",
        }
        category_dataset.append([category_values.get(header, "") for header in category_dataset.headers])
        category_result = category_resource.import_data(category_dataset, dry_run=True, raise_errors=False)

        self.assertFalse(category_result.has_errors())
        self.assertFalse(Category.objects.filter(slug="imported-category-dry-run").exists())

    def test_consultation_request_admin_is_registered_and_exportable(self):
        user = User.objects.create_user(username="consult-admin-check")
        customer = Customer.objects.create(
            user=user,
            full_name="Consult Admin Customer",
            phone_number="0900000001",
            address="Ha Noi",
        )
        consultation_request = ConsultationRequest.objects.create(
            customer=customer,
            name="Consult Admin Customer",
            phone="0900000001",
            message="Need product advice.",
        )
        consultation_request.items.create(product=self.product, quantity=2)

        self.assertIn(ConsultationRequest, admin.site._registry)
        consultation_admin = admin.site._registry[ConsultationRequest]
        resource = consultation_admin.get_resource_classes(self.request)[0]()
        exported = resource.export(ConsultationRequest.objects.filter(pk=consultation_request.pk))

        self.assertEqual(exported.height, 1)
        self.assertIn("status", exported.headers)
        self.assertIn("phone", exported.headers)


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
        suffix = Customer.objects.count() + 1
        return Customer.objects.create(
            user=user,
            full_name=f"Kh?ch {username}",
            email=email,
            phone_number=f"090000{suffix:04d}",
            address="H? N?i",
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




