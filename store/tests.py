from django.test import TestCase
from django.urls import reverse

from .models import CartItem, Category, Product
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
        self.assertContains(response, "7,500,000 d")

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
