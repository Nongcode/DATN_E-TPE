from decimal import Decimal

from django import template
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum

from store.models import Category, Customer, Inventory, Order, OrderItem, Product, Voucher


register = template.Library()


def _money(value):
    try:
        amount = Decimal(value or 0)
    except Exception:
        amount = Decimal("0")
    return f"{amount:,.0f} đ"


@register.filter
def admin_vnd(value):
    return _money(value)


def _month_value(month_date):
    return month_date.strftime("%Y-%m")


def _month_label(month_date):
    return f"Tháng {month_date.month}/{month_date.year}"


@register.simple_tag(takes_context=True)
def admin_dashboard_data(context):
    request = context.get("request")
    selected_customer_month = "all"
    if request:
        selected_customer_month = request.GET.get("customer_month", "all") or "all"

    available_months = list(Order.objects.dates("created_at", "month", order="DESC"))
    month_values = {_month_value(month) for month in available_months}
    if selected_customer_month not in month_values:
        selected_customer_month = "all"

    customer_month_options = [
        {
            "value": "all",
            "label": "Tất cả thời gian",
            "selected": selected_customer_month == "all",
        }
    ]
    for month in available_months:
        value = _month_value(month)
        customer_month_options.append(
            {
                "value": value,
                "label": _month_label(month),
                "selected": selected_customer_month == value,
            }
        )

    line_total = ExpressionWrapper(
        F("price") * F("quantity"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )

    low_stock_count = Inventory.objects.filter(quantity__lte=F("low_stock_threshold")).count()
    pending_orders = Order.objects.filter(status="Pending").count()

    top_products_qs = (
        OrderItem.objects.exclude(order__status="Cancelled")
        .values("product_id", "product__name", "product__sku")
        .annotate(sold_total=Sum("quantity"), revenue=Sum(line_total))
        .order_by("-sold_total", "product__name")[:8]
    )
    top_products = list(top_products_qs)
    max_sold = max([item["sold_total"] or 0 for item in top_products] or [0])
    for item in top_products:
        item["bar_percent"] = int(((item["sold_total"] or 0) / max_sold) * 100) if max_sold else 0
        item["revenue_display"] = _money(item.get("revenue"))
        item["short_name"] = item["product__name"][:22] + ("..." if len(item["product__name"]) > 22 else "")

    customer_orders = Order.objects.exclude(status="Cancelled")
    selected_customer_period_label = "Tất cả thời gian"
    if selected_customer_month != "all":
        year, month = selected_customer_month.split("-", 1)
        customer_orders = customer_orders.filter(created_at__year=int(year), created_at__month=int(month))
        selected_customer_period_label = f"Tháng {int(month)}/{year}"

    top_customers_qs = (
        customer_orders.values("customer_id", "customer__full_name", "customer__user__username")
        .annotate(order_count=Count("id"), total_spent=Sum("total_amount"))
        .order_by("-total_spent", "customer__full_name")[:5]
    )
    top_customers = []
    for index, item in enumerate(top_customers_qs, start=1):
        item["rank"] = index
        item["display_name"] = item["customer__full_name"] or item["customer__user__username"]
        item["total_spent_display"] = _money(item.get("total_spent"))
        top_customers.append(item)

    order_statuses = {
        row["status"]: row["total"]
        for row in customer_orders.values("status").annotate(total=Count("id"))
    }

    stats = [
        {
            "label": "Sản phẩm",
            "value": Product.objects.count(),
            "url": "/admin/store/product/",
            "icon": "fas fa-box-open",
            "tone": "blue",
        },
        {
            "label": "Khách hàng",
            "value": Customer.objects.count(),
            "url": "/admin/store/customer/",
            "icon": "fas fa-users",
            "tone": "green",
        },
        {
            "label": "Đơn hàng mới",
            "value": pending_orders,
            "url": "/admin/store/order/?status__exact=Pending",
            "icon": "fas fa-shopping-bag",
            "tone": "orange",
        },
        {
            "label": "Sắp hết hàng",
            "value": low_stock_count,
            "url": "/admin/store/inventory/",
            "icon": "fas fa-exclamation-triangle",
            "tone": "red",
        },
        {
            "label": "Danh mục sản phẩm",
            "value": Category.objects.count(),
            "url": "/admin/store/category/",
            "icon": "fas fa-layer-group",
            "tone": "purple",
        },
        {
            "label": "Mã voucher",
            "value": Voucher.objects.count(),
            "url": "/admin/store/voucher/",
            "icon": "fas fa-ticket-alt",
            "tone": "teal",
        },
    ]

    return {
        "stats": stats,
        "top_products": top_products,
        "top_customers": top_customers,
        "order_count": customer_orders.count(),
        "order_statuses": order_statuses,
        "total_revenue": Order.objects.exclude(status="Cancelled").aggregate(total=Sum("total_amount"))["total"] or 0,
        "customer_month_options": customer_month_options,
        "selected_customer_month": selected_customer_month,
        "selected_customer_period_label": selected_customer_period_label,
    }