from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportModelAdmin

from .models import (
    Blog,
    Cart,
    CartItem,
    Category,
    ConsultationRequest,
    ConsultationRequestItem,
    Customer,
    Inventory,
    Order,
    OrderItem,
    Product,
    ProductImage,
    RecommendationLog,
    ScheduledTask,
    Voucher,
)
from .background_tasks import execute_scheduled_task, is_recurring_daily_task


def action_buttons_for(obj, admin_name):
    edit_url = reverse(f"admin:{admin_name}_change", args=[obj.pk])
    delete_url = reverse(f"admin:{admin_name}_delete", args=[obj.pk])
    return format_html(
        '<div class="product-actions">'
        '<a class="btn btn-sm btn-info text-white" href="{}" style="margin-right: 5px;">'
        '<i class="fas fa-edit"></i> Sửa</a>'
        '<a class="btn btn-sm btn-danger text-white" href="{}">'
        '<i class="fas fa-trash"></i> Xóa</a>'
        '</div>',
        edit_url,
        delete_url,
    )


ADMIN_LIST_PER_PAGE = 8


class ProductCountFilter(admin.SimpleListFilter):
    title = "Số lượng SP"
    parameter_name = "product_count"

    def lookups(self, request, model_admin):
        return (
            ("0", "0 sản phẩm"),
            ("1_10", "1 - 10 sản phẩm"),
            ("10+", "Trên 10 sản phẩm"),
        )

    def queryset(self, request, queryset):
        qs = queryset.annotate(p_count=Count("products"))
        if self.value() == "0":
            return qs.filter(p_count=0)
        if self.value() == "1_10":
            return qs.filter(p_count__gte=1, p_count__lte=10)
        if self.value() == "10+":
            return qs.filter(p_count__gt=10)
        return queryset


@admin.register(Category)
class CategoryAdmin(ImportExportModelAdmin):
    list_display = ("name", "parent", "status_badge", "get_product_count", "action_buttons")
    list_filter = ("status", "parent", ProductCountFilter)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = ADMIN_LIST_PER_PAGE

    def get_product_count(self, obj):
        count = Product.objects.filter(category=obj).count()
        return format_html('<span class="badge bg-secondary">{} sản phẩm</span>', count)

    get_product_count.short_description = "Số lượng SP"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_category")

    action_buttons.short_description = "Thao tác"

    def status_badge(self, obj):
        if obj.status == "visible":
            return format_html(
                '<span class="badge" style="background-color: #10b981; font-size: 13px; padding: 5px 10px;">{}</span>',
                "Hiển thị",
            )
        if obj.status == "hidden":
            return format_html(
                '<span class="badge" style="background-color: #64748b; font-size: 13px; padding: 5px 10px;">{}</span>',
                "Ẩn",
            )
        if obj.status == "out_of_stock":
            return format_html(
                '<span class="badge" style="background-color: #f59e0b; color: white; font-size: 13px; padding: 5px 10px;">{}</span>',
                "Hết hàng",
            )
        return obj.status

    status_badge.short_description = "Trạng thái"


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3

@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    inlines = [ProductImageInline]
    list_display = (
        "product_preview",
        "name",
        "category",
        "sku_badge",
        "brand_badge",
        "compatibility_badge",
        "price_display",
        "active_badge",
        "action_buttons",
    )
    list_filter = ("is_active", "category", "brand", "manufacturer", "created_at")
    list_display_links = ("name",)
    search_fields = (
        "name",
        "sku",
        "brand",
        "manufacturer",
        "compatible_car_brands",
        "compatible_car_models",
        "category__name",
    )
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = ADMIN_LIST_PER_PAGE

    def product_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" class="admin-product-thumb" alt="{}">', obj.image.url, obj.name)
        return mark_safe(
            '<span class="admin-product-thumb admin-product-thumb--empty"><i class="fas fa-box-open"></i></span>'
        )

    product_preview.short_description = ""

    def sku_badge(self, obj):
        return format_html('<span class="product-sku">{}</span>', obj.sku or "Chưa có SKU")

    sku_badge.short_description = "SKU"

    def brand_badge(self, obj):
        if obj.brand:
            return format_html('<span class="badge bg-light text-dark">{}</span>', obj.brand)
        return "-"

    brand_badge.short_description = "Thương hiệu"

    def compatibility_badge(self, obj):
        car_brands = obj.compatible_car_brands or "-"
        car_models = obj.compatible_car_models or "-"
        return format_html(
            '<span class="text-nowrap"><strong>Hãng xe:</strong> {}<br><strong>Dòng xe:</strong> {}</span>',
            car_brands,
            car_models,
        )

    compatibility_badge.short_description = "Tương thích"

    def price_display(self, obj):
        price = f"{obj.price:,.0f}" if obj.price is not None else "0"
        return format_html('<span class="product-price">{} d</span>', price)

    price_display.short_description = "Giá bán"

    def active_badge(self, obj):
        if obj.is_active:
            return mark_safe('<span class="product-status product-status--active">Đang hiển thị</span>')
        return mark_safe('<span class="product-status product-status--hidden">Đang ẩn</span>')

    active_badge.short_description = "Trạng thái"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_product")

    action_buttons.short_description = "Thao tác"


@admin.register(Inventory)
class InventoryAdmin(ImportExportModelAdmin):
    list_display = ("product", "quantity_badge", "low_stock_threshold", "stock_badge", "last_updated", "action_buttons")
    list_display_links = ("product",)
    search_fields = ("product__name", "product__sku")
    list_filter = ("last_updated",)
    list_select_related = ("product",)
    list_per_page = ADMIN_LIST_PER_PAGE

    def quantity_badge(self, obj):
        return format_html('<span class="product-sku">{} SP</span>', obj.quantity)

    quantity_badge.short_description = "Tồn kho"

    def stock_badge(self, obj):
        if obj.quantity <= 0:
            return mark_safe('<span class="product-status product-status--danger">Hết hàng</span>')
        if obj.quantity <= obj.low_stock_threshold:
            return mark_safe('<span class="product-status product-status--hidden">Sắp hết</span>')
        return mark_safe('<span class="product-status product-status--active">Còn hàng</span>')

    stock_badge.short_description = "Cảnh báo"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_inventory")

    action_buttons.short_description = "Thao tác"


@admin.register(Customer)
class CustomerAdmin(ImportExportModelAdmin):
    list_display = ("customer_name", "username", "email", "phone_number", "date_of_birth", "address", "action_buttons")
    list_display_links = ("customer_name",)
    search_fields = ("full_name", "user__username", "email", "phone_number", "address")
    list_filter = ("date_of_birth",)
    list_per_page = ADMIN_LIST_PER_PAGE

    def customer_name(self, obj):
        return obj.full_name or obj.user.get_full_name() or obj.user.username

    customer_name.short_description = "Khách hàng"

    def username(self, obj):
        return obj.user.username

    username.short_description = "Tài khoản"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_customer")

    action_buttons.short_description = "Thao tác"


@admin.register(Voucher)
class VoucherAdmin(ImportExportModelAdmin):
    list_display = ("code", "customer", "discount_display", "valid_until", "used_badge", "action_buttons")
    list_display_links = ("code",)
    list_filter = ("is_used", "valid_until")
    search_fields = ("code", "customer__full_name", "customer__user__username")
    list_per_page = ADMIN_LIST_PER_PAGE

    def discount_display(self, obj):
        amount = f"{obj.discount_amount:,.0f}" if obj.discount_amount is not None else "0"
        return format_html('<span class="product-price">{} d</span>', amount)

    discount_display.short_description = "Giá trị"

    def used_badge(self, obj):
        if obj.is_used:
            return mark_safe('<span class="product-status product-status--hidden">Đã sử dụng</span>')
        return mark_safe('<span class="product-status product-status--active">Còn hiệu lực</span>')

    used_badge.short_description = "Trạng thái"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_voucher")

    action_buttons.short_description = "Thao tác"


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ("product", "quantity", "line_total")
    readonly_fields = ("line_total",)
    autocomplete_fields = ("product",)

    def line_total(self, obj):
        if not obj.pk:
            return "-"
        total = (obj.product.price or 0) * obj.quantity
        return f"{total:,.0f} d"

    line_total.short_description = "Thành tiền"


@admin.register(Cart)
class CartAdmin(ImportExportModelAdmin):
    list_display = ("cart_label", "user", "item_count", "cart_total", "created_at", "updated_at", "action_buttons")
    list_display_links = ("cart_label",)
    search_fields = ("id", "user__username", "items__product__name", "items__product__sku")
    list_filter = ("created_at", "updated_at")
    inlines = (CartItemInline,)
    list_per_page = ADMIN_LIST_PER_PAGE

    def cart_label(self, obj):
        return f"Giỏ hàng #{obj.id}"

    cart_label.short_description = "Giỏ hàng"

    def item_count(self, obj):
        return sum(item.quantity for item in obj.items.all())

    item_count.short_description = "Số lượng"

    def cart_total(self, obj):
        total = sum((item.product.price or 0) * item.quantity for item in obj.items.select_related("product"))
        return format_html('<span class="product-price">{} d</span>', f"{total:,.0f}")

    cart_total.short_description = "Tạm tính"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_cart")

    action_buttons.short_description = "Thao tác"


@admin.register(Order)
class OrderAdmin(ImportExportModelAdmin):
    list_display = ("order_label", "customer", "voucher", "total_display", "status_badge", "created_at", "action_buttons")
    list_display_links = ("order_label",)
    list_filter = ("status", "created_at")
    search_fields = ("id", "customer__full_name", "customer__user__username", "voucher__code")
    list_per_page = ADMIN_LIST_PER_PAGE

    def order_label(self, obj):
        return f"Đơn hàng #{obj.id}"

    order_label.short_description = "Đơn hàng"

    def total_display(self, obj):
        total = f"{obj.total_amount:,.0f}" if obj.total_amount is not None else "0"
        return format_html('<span class="product-price">{} d</span>', total)

    total_display.short_description = "Tổng tiền"

    def status_badge(self, obj):
        status_map = {
            "Pending": '<span class="product-status product-status--hidden">Chờ xử lý</span>',
            "Confirmed": '<span class="product-status product-status--active">Đã lên đơn</span>',
            "Shipping": '<span class="product-status product-status--hidden">Đang vận chuyển</span>',
            "Shipped": '<span class="product-status product-status--active">Đã giao hàng</span>',
            "Cancelled": '<span class="product-status product-status--danger">Đã hủy</span>',
        }
        return mark_safe(status_map.get(obj.status, obj.status))

    status_badge.short_description = "Trạng thái"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_order")

    action_buttons.short_description = "Thao tác"


@admin.register(OrderItem)
class OrderItemAdmin(ImportExportModelAdmin):
    list_display = ("order", "product", "price_display", "quantity", "line_total", "action_buttons")
    list_display_links = ("order",)
    search_fields = ("order__id", "product__name", "product__sku")
    list_filter = ("order__created_at",)
    list_per_page = ADMIN_LIST_PER_PAGE

    def price_display(self, obj):
        price = f"{obj.price:,.0f}" if obj.price is not None else "0"
        return format_html('<span class="product-price">{} d</span>', price)

    price_display.short_description = "Giá"

    def line_total(self, obj):
        total = (obj.price or 0) * obj.quantity
        return format_html('<span class="product-price">{} d</span>', f"{total:,.0f}")

    line_total.short_description = "Thành tiền"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_orderitem")

    action_buttons.short_description = "Thao tác"


@admin.register(CartItem)
class CartItemAdmin(ImportExportModelAdmin):
    list_display = ("cart", "product", "quantity", "line_total", "action_buttons")
    list_display_links = ("cart",)
    search_fields = ("cart__id", "product__name", "product__sku")
    list_filter = ("cart__created_at",)
    list_select_related = ("cart", "product")
    list_per_page = ADMIN_LIST_PER_PAGE

    def line_total(self, obj):
        total = (obj.product.price or 0) * obj.quantity
        return format_html('<span class="product-price">{} d</span>', f"{total:,.0f}")

    line_total.short_description = "Thành tiền"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_cartitem")

    action_buttons.short_description = "Thao tác"


class ConsultationRequestItemInline(admin.TabularInline):
    model = ConsultationRequestItem
    extra = 0
    fields = ("product", "quantity", "line_total")
    readonly_fields = ("line_total",)
    autocomplete_fields = ("product",)

    def line_total(self, obj):
        if not obj.pk:
            return "-"
        total = (obj.product.price or 0) * obj.quantity
        return f"{total:,.0f} d"

    line_total.short_description = "Tạm tính"


@admin.register(ConsultationRequest)
class ConsultationRequestAdmin(ImportExportModelAdmin):
    list_display = (
        "request_label",
        "customer",
        "phone",
        "status_badge",
        "product_summary",
        "created_at",
        "action_buttons",
    )
    list_display_links = ("request_label",)
    list_filter = ("status", "created_at", "updated_at")
    search_fields = (
        "id",
        "name",
        "phone",
        "email",
        "customer__full_name",
        "customer__user__username",
        "items__product__name",
        "items__product__sku",
        "message",
    )
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("customer", "customer__user")
    inlines = (ConsultationRequestItemInline,)
    actions = ("mark_contacted", "mark_converted", "mark_cancelled")
    list_per_page = ADMIN_LIST_PER_PAGE

    def request_label(self, obj):
        return f"Yêu cầu #{obj.id}"

    request_label.short_description = "Yêu cầu"

    def product_summary(self, obj):
        items = list(obj.items.select_related("product")[:3])
        if not items:
            return "-"
        labels = [f"{item.product.name} x{item.quantity}" for item in items]
        extra_count = obj.items.count() - len(items)
        if extra_count > 0:
            labels.append(f"+{extra_count} sản phẩm khác")
        return ", ".join(labels)

    product_summary.short_description = "Sản phẩm"

    def status_badge(self, obj):
        status_map = {
            "pending": '<span class="product-status product-status--hidden">Chờ tư vấn</span>',
            "contacted": '<span class="product-status product-status--active">Đã liên hệ</span>',
            "converted": '<span class="product-status product-status--active">Đã lên đơn</span>',
            "cancelled": '<span class="product-status product-status--danger">Đã hủy</span>',
        }
        return mark_safe(status_map.get(obj.status, obj.status))

    status_badge.short_description = "Trạng thái"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_consultationrequest")

    action_buttons.short_description = "Thao tác"

    def mark_contacted(self, request, queryset):
        updated = queryset.update(status="contacted")
        self.message_user(request, f"Đã đánh dấu {updated} yêu cầu là đã liên hệ.")

    mark_contacted.short_description = "Đánh dấu đã liên hệ"

    def mark_converted(self, request, queryset):
        updated = queryset.update(status="converted")
        self.message_user(request, f"Đã đánh dấu {updated} yêu cầu là đã lên đơn.")

    mark_converted.short_description = "Đánh dấu đã lên đơn"

    def mark_cancelled(self, request, queryset):
        updated = queryset.update(status="cancelled")
        self.message_user(request, f"Đã hủy {updated} yêu cầu tư vấn.")

    mark_cancelled.short_description = "Đánh dấu đã hủy"


@admin.register(Blog)
class BlogAdmin(ImportExportModelAdmin):
    list_display = ("title", "author", "created_at", "action_buttons")
    list_display_links = ("title",)
    search_fields = ("title", "content", "author__username")
    list_filter = ("created_at", "author")
    list_select_related = ("author",)
    list_per_page = ADMIN_LIST_PER_PAGE

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_blog")

    action_buttons.short_description = "Thao tác"


@admin.register(RecommendationLog)
class RecommendationLogAdmin(ImportExportModelAdmin):
    list_display = ("user", "product", "interaction_type", "created_at")
    search_fields = ("user__username", "product__name", "product__sku")
    list_filter = ("interaction_type", "created_at")
    list_select_related = ("user", "product")
    list_per_page = ADMIN_LIST_PER_PAGE


@admin.register(ScheduledTask)
class ScheduledTaskAdmin(ImportExportModelAdmin):
    list_display = ("task_type_badge", "status_badge", "run_at", "execution_preview", "created_at", "action_buttons")
    list_display_links = ("task_type_badge",)
    search_fields = ("task_type", "status", "execution_log")
    list_filter = ("task_type", "status", "run_at")
    list_per_page = ADMIN_LIST_PER_PAGE
    actions = ("execute_selected_tasks", "reset_to_pending")

    def task_type_badge(self, obj):
        labels = {
            "lock_stock": ("Cảnh báo tồn kho", "#0f766e"),
            "birthday_mail": ("Email sinh nhật", "#2563eb"),
            "auto_hide": ("Ẩn hết hàng", "#7c3aed"),
        }
        label, color = labels.get(obj.task_type, (obj.task_type, "#334155"))
        return format_html(
            '<span class="badge" style="background-color: {}; font-size: 13px; padding: 5px 10px;">{}</span>',
            color,
            label,
        )

    task_type_badge.short_description = "Loại tác vụ"

    def status_badge(self, obj):
        if obj.status == "success":
            return mark_safe('<span class="product-status product-status--active">Thành công</span>')
        if obj.status == "failed":
            return mark_safe('<span class="product-status product-status--danger">Thất bại</span>')
        if is_recurring_daily_task(obj):
            return mark_safe('<span class="product-status product-status--hidden">Đã lên lịch</span>')
        return mark_safe('<span class="product-status product-status--hidden">Chờ xử lý</span>')

    status_badge.short_description = "Trạng thái"

    def execution_preview(self, obj):
        if not obj.execution_log:
            return "-"
        return obj.execution_log[:120] + ("..." if len(obj.execution_log) > 120 else "")

    execution_preview.short_description = "Kết quả gần nhất"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_scheduledtask")

    action_buttons.short_description = "Thao tác"

    def execute_selected_tasks(self, request, queryset):
        success_count = 0
        failed_count = 0
        for task in queryset:
            result = execute_scheduled_task(task)
            if result.message.startswith("failed:"):
                failed_count += 1
            else:
                success_count += 1

        self.message_user(
            request,
            f"Đã chạy {success_count} tác vụ thành công, {failed_count} tác vụ thất bại.",
        )

    execute_selected_tasks.short_description = "Chạy ngay tác vụ đã chọn"

    def reset_to_pending(self, request, queryset):
        updated = queryset.update(status="pending")
        self.message_user(request, f"Đã đưa {updated} tác vụ về trạng thái chờ xử lý.")

    reset_to_pending.short_description = "Đưa về trạng thái chờ xử lý"
