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
    Customer,
    Inventory,
    Order,
    OrderItem,
    Product,
    RecommendationLog,
    ScheduledTask,
    Voucher,
)


def action_buttons_for(obj, admin_name):
    edit_url = reverse(f"admin:{admin_name}_change", args=[obj.pk])
    delete_url = reverse(f"admin:{admin_name}_delete", args=[obj.pk])
    return format_html(
        '<div class="product-actions">'
        '<a class="btn btn-sm btn-info text-white" href="{}" style="margin-right: 5px;">'
        '<i class="fas fa-edit"></i> Sua</a>'
        '<a class="btn btn-sm btn-danger text-white" href="{}">'
        '<i class="fas fa-trash"></i> Xoa</a>'
        '</div>',
        edit_url,
        delete_url,
    )


class ProductCountFilter(admin.SimpleListFilter):
    title = "So luong SP"
    parameter_name = "product_count"

    def lookups(self, request, model_admin):
        return (
            ("0", "0 san pham"),
            ("1_10", "1 - 10 san pham"),
            ("10+", "Tren 10 san pham"),
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

    def get_product_count(self, obj):
        count = Product.objects.filter(category=obj).count()
        return format_html('<span class="badge bg-secondary">{} san pham</span>', count)

    get_product_count.short_description = "So luong SP"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_category")

    action_buttons.short_description = "Thao tac"

    def status_badge(self, obj):
        if obj.status == "visible":
            return format_html(
                '<span class="badge" style="background-color: #10b981; font-size: 13px; padding: 5px 10px;">{}</span>',
                "Hien thi",
            )
        if obj.status == "hidden":
            return format_html(
                '<span class="badge" style="background-color: #64748b; font-size: 13px; padding: 5px 10px;">{}</span>',
                "An",
            )
        if obj.status == "out_of_stock":
            return format_html(
                '<span class="badge" style="background-color: #f59e0b; color: white; font-size: 13px; padding: 5px 10px;">{}</span>',
                "Het hang",
            )
        return obj.status

    status_badge.short_description = "Trang thai"


@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    list_display = (
        "product_preview",
        "name",
        "category",
        "sku_badge",
        "price_display",
        "active_badge",
        "action_buttons",
    )
    list_filter = ("is_active", "category", "created_at")
    list_display_links = ("name",)
    search_fields = ("name", "sku", "category__name")
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 12

    def product_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" class="admin-product-thumb" alt="{}">', obj.image.url, obj.name)
        return mark_safe(
            '<span class="admin-product-thumb admin-product-thumb--empty"><i class="fas fa-box-open"></i></span>'
        )

    product_preview.short_description = ""

    def sku_badge(self, obj):
        return format_html('<span class="product-sku">{}</span>', obj.sku or "Chua co SKU")

    sku_badge.short_description = "SKU"

    def price_display(self, obj):
        price = f"{obj.price:,.0f}" if obj.price is not None else "0"
        return format_html('<span class="product-price">{} d</span>', price)

    price_display.short_description = "Gia ban"

    def active_badge(self, obj):
        if obj.is_active:
            return mark_safe('<span class="product-status product-status--active">Dang hien thi</span>')
        return mark_safe('<span class="product-status product-status--hidden">Dang an</span>')

    active_badge.short_description = "Trang thai"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_product")

    action_buttons.short_description = "Thao tac"


@admin.register(Inventory)
class InventoryAdmin(ImportExportModelAdmin):
    list_display = ("product", "quantity_badge", "low_stock_threshold", "stock_badge", "last_updated", "action_buttons")
    list_display_links = ("product",)
    search_fields = ("product__name", "product__sku")
    list_filter = ("last_updated",)
    list_select_related = ("product",)
    list_per_page = 12

    def quantity_badge(self, obj):
        return format_html('<span class="product-sku">{} sp</span>', obj.quantity)

    quantity_badge.short_description = "Ton kho"

    def stock_badge(self, obj):
        if obj.quantity <= 0:
            return mark_safe('<span class="product-status product-status--danger">Het hang</span>')
        if obj.quantity <= obj.low_stock_threshold:
            return mark_safe('<span class="product-status product-status--hidden">Sap het</span>')
        return mark_safe('<span class="product-status product-status--active">Con hang</span>')

    stock_badge.short_description = "Canh bao"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_inventory")

    action_buttons.short_description = "Thao tac"


@admin.register(Customer)
class CustomerAdmin(ImportExportModelAdmin):
    list_display = ("customer_name", "username", "email", "phone_number", "address", "action_buttons")
    list_display_links = ("customer_name",)
    search_fields = ("full_name", "user__username", "email", "phone_number", "address")
    list_per_page = 12

    def customer_name(self, obj):
        return obj.full_name or obj.user.get_full_name() or obj.user.username

    customer_name.short_description = "Khach hang"

    def username(self, obj):
        return obj.user.username

    username.short_description = "Tai khoan"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_customer")

    action_buttons.short_description = "Thao tac"


@admin.register(Voucher)
class VoucherAdmin(ImportExportModelAdmin):
    list_display = ("code", "customer", "discount_display", "valid_until", "used_badge", "action_buttons")
    list_display_links = ("code",)
    list_filter = ("is_used", "valid_until")
    search_fields = ("code", "customer__full_name", "customer__user__username")
    list_per_page = 12

    def discount_display(self, obj):
        amount = f"{obj.discount_amount:,.0f}" if obj.discount_amount is not None else "0"
        return format_html('<span class="product-price">{} d</span>', amount)

    discount_display.short_description = "Gia tri"

    def used_badge(self, obj):
        if obj.is_used:
            return mark_safe('<span class="product-status product-status--hidden">Da su dung</span>')
        return mark_safe('<span class="product-status product-status--active">Con hieu luc</span>')

    used_badge.short_description = "Trang thai"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_voucher")

    action_buttons.short_description = "Thao tac"


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

    line_total.short_description = "Thanh tien"


@admin.register(Cart)
class CartAdmin(ImportExportModelAdmin):
    list_display = ("cart_label", "user", "item_count", "cart_total", "created_at", "updated_at", "action_buttons")
    list_display_links = ("cart_label",)
    search_fields = ("id", "user__username", "items__product__name", "items__product__sku")
    list_filter = ("created_at", "updated_at")
    inlines = (CartItemInline,)
    list_per_page = 12

    def cart_label(self, obj):
        return f"Gio hang #{obj.id}"

    cart_label.short_description = "Gio hang"

    def item_count(self, obj):
        return sum(item.quantity for item in obj.items.all())

    item_count.short_description = "So luong"

    def cart_total(self, obj):
        total = sum((item.product.price or 0) * item.quantity for item in obj.items.select_related("product"))
        return format_html('<span class="product-price">{} d</span>', f"{total:,.0f}")

    cart_total.short_description = "Tam tinh"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_cart")

    action_buttons.short_description = "Thao tac"


@admin.register(Order)
class OrderAdmin(ImportExportModelAdmin):
    list_display = ("order_label", "customer", "voucher", "total_display", "status_badge", "created_at", "action_buttons")
    list_display_links = ("order_label",)
    list_filter = ("status", "created_at")
    search_fields = ("id", "customer__full_name", "customer__user__username", "voucher__code")
    list_per_page = 12

    def order_label(self, obj):
        return f"Don hang #{obj.id}"

    order_label.short_description = "Don hang"

    def total_display(self, obj):
        total = f"{obj.total_amount:,.0f}" if obj.total_amount is not None else "0"
        return format_html('<span class="product-price">{} d</span>', total)

    total_display.short_description = "Tong tien"

    def status_badge(self, obj):
        status_map = {
            "Pending": '<span class="product-status product-status--hidden">Cho xu ly</span>',
            "Shipped": '<span class="product-status product-status--active">Da giao hang</span>',
            "Cancelled": '<span class="product-status product-status--danger">Da huy</span>',
        }
        return mark_safe(status_map.get(obj.status, obj.status))

    status_badge.short_description = "Trang thai"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_order")

    action_buttons.short_description = "Thao tac"


@admin.register(OrderItem)
class OrderItemAdmin(ImportExportModelAdmin):
    list_display = ("order", "product", "price_display", "quantity", "line_total", "action_buttons")
    list_display_links = ("order",)
    search_fields = ("order__id", "product__name", "product__sku")
    list_filter = ("order__created_at",)
    list_per_page = 12

    def price_display(self, obj):
        price = f"{obj.price:,.0f}" if obj.price is not None else "0"
        return format_html('<span class="product-price">{} d</span>', price)

    price_display.short_description = "Gia"

    def line_total(self, obj):
        total = (obj.price or 0) * obj.quantity
        return format_html('<span class="product-price">{} d</span>', f"{total:,.0f}")

    line_total.short_description = "Thanh tien"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_orderitem")

    action_buttons.short_description = "Thao tac"


@admin.register(CartItem)
class CartItemAdmin(ImportExportModelAdmin):
    list_display = ("cart", "product", "quantity", "line_total", "action_buttons")
    list_display_links = ("cart",)
    search_fields = ("cart__id", "product__name", "product__sku")
    list_filter = ("cart__created_at",)
    list_select_related = ("cart", "product")
    list_per_page = 12

    def line_total(self, obj):
        total = (obj.product.price or 0) * obj.quantity
        return format_html('<span class="product-price">{} d</span>', f"{total:,.0f}")

    line_total.short_description = "Thanh tien"

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_cartitem")

    action_buttons.short_description = "Thao tac"


@admin.register(Blog)
class BlogAdmin(ImportExportModelAdmin):
    list_display = ("title", "author", "created_at", "action_buttons")
    list_display_links = ("title",)
    search_fields = ("title", "content", "author__username")
    list_filter = ("created_at", "author")
    list_select_related = ("author",)
    list_per_page = 12

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_blog")

    action_buttons.short_description = "Thao tac"


@admin.register(RecommendationLog)
class RecommendationLogAdmin(ImportExportModelAdmin):
    list_display = ("user", "product", "interaction_type", "created_at")
    search_fields = ("user__username", "product__name", "product__sku")
    list_filter = ("interaction_type", "created_at")
    list_select_related = ("user", "product")
    list_per_page = 12


@admin.register(ScheduledTask)
class ScheduledTaskAdmin(ImportExportModelAdmin):
    list_display = ("task_type", "status", "run_at", "created_at", "action_buttons")
    list_display_links = ("task_type",)
    search_fields = ("task_type", "status", "execution_log")
    list_filter = ("task_type", "status", "run_at")
    list_per_page = 12

    def action_buttons(self, obj):
        return action_buttons_for(obj, "store_scheduledtask")

    action_buttons.short_description = "Thao tac"
