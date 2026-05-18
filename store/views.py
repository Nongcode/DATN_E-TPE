from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import Blog, Cart, CartItem, Category, Product, RecommendationLog
from .search import search_products


def _active_products():
    return Product.objects.select_related("category").filter(
        is_active=True,
        category__status="visible",
    )


def _visible_categories():
    return Category.objects.filter(status="visible")


def _get_current_cart(request, create=False):
    cart = None
    session_cart_id = request.session.get("cart_id")

    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).order_by("-updated_at").first()
        if not cart:
            cart = Cart.objects.create(user=request.user)
        if session_cart_id:
            session_cart = (
                Cart.objects.filter(pk=session_cart_id, user__isnull=True)
                .prefetch_related("items")
                .first()
            )
            if session_cart and session_cart.pk != cart.pk:
                for item in session_cart.items.select_related("product"):
                    _upsert_cart_item(cart, item.product, item.quantity)
                session_cart.delete()
            request.session.pop("cart_id", None)
        return cart

    if session_cart_id:
        cart = Cart.objects.filter(pk=session_cart_id, user__isnull=True).first()
        if cart:
            return cart
        request.session.pop("cart_id", None)

    if create:
        cart = Cart.objects.create()
        request.session["cart_id"] = cart.pk
        request.session.modified = True
        return cart

    return None


def _upsert_cart_item(cart, product, quantity):
    item = CartItem.objects.filter(cart=cart, product=product).first()
    if item:
        item.quantity += quantity
        item.save(update_fields=["quantity"])
        return item
    return CartItem.objects.create(cart=cart, product=product, quantity=quantity)


def _get_cart_item_or_404(request, item_id):
    cart = _get_current_cart(request, create=False)
    if not cart:
        raise Http404("Cart item not found")
    return get_object_or_404(CartItem.objects.select_related("product"), pk=item_id, cart=cart)


def _cart_summary(request):
    cart = _get_current_cart(request, create=False)
    if not cart:
        return {"cart": None, "cart_item_count": 0, "cart_total": 0}

    items = list(cart.items.select_related("product"))
    item_count = sum(item.quantity for item in items)
    total = sum(item.product.price * item.quantity for item in items)
    return {"cart": cart, "cart_item_count": item_count, "cart_total": total}


def _editorial_context():
    news_posts = list(Blog.objects.select_related("author").order_by("-created_at")[:3])
    fallback_news = [
        {
            "id": "fallback-1",
            "title": "5 bước chăm sóc nội thất xe luôn sạch và bền màu",
            "excerpt": "Những bước vệ sinh, dưỡng bề mặt và khử mùi cơ bản để khoang lái luôn gọn gàng, dễ chịu mỗi ngày.",
            "tag": "Chăm sóc xe",
            "image": "https://images.unsplash.com/photo-1489824904134-891ab64532f1?auto=format&fit=crop&w=1200&q=80",
        },
        {
            "id": "fallback-2",
            "title": "Khi nào nên thay dầu nhớt để động cơ vận hành ổn định?",
            "excerpt": "Các dấu hiệu nhận biết thời điểm thay dầu, cách chọn độ nhớt phù hợp và lưu ý để bảo vệ động cơ tốt hơn.",
            "tag": "Kỹ thuật xe",
            "image": "https://images.unsplash.com/photo-1489824904134-891ab64532f1?auto=format&fit=crop&w=1200&q=80",
        },
        {
            "id": "fallback-3",
            "title": "ETEK Store mở rộng dịch vụ tư vấn và lắp đặt tại cửa hàng",
            "excerpt": "Khách hàng có thể trải nghiệm tư vấn trực tiếp, kiểm tra cấu hình và lắp đặt phụ kiện ngay tại showroom.",
            "tag": "Thông tin cửa hàng",
            "image": "https://images.unsplash.com/photo-1449965408869-eaa3f722e40d?auto=format&fit=crop&w=1200&q=80",
        },
    ]
    partner_brands = [
        {
            "name": "Michelin",
            "logo": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Michelin_Wordmark.svg",
            "fallback_logo": "/static/img/brands/michelin.svg",
        },
        {
            "name": "Bosch",
            "logo": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Bosch-logo.svg",
            "fallback_logo": "/static/img/brands/bosch.svg",
        },
        {
            "name": "Shell",
            "logo": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Shell_wordmark_2019.svg",
            "fallback_logo": "/static/img/brands/shell.svg",
        },
        {
            "name": "3M",
            "logo": "https://commons.wikimedia.org/wiki/Special:Redirect/file/3M_wordmark.svg",
            "fallback_logo": "/static/img/brands/3m.svg",
        },
        {
            "name": "Pioneer",
            "logo": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Pioneer_(logo).svg",
            "fallback_logo": "/static/img/brands/pioneer.svg",
        },
        {
            "name": "VietMap",
            "logo": "https://www.google.com/s2/favicons?domain=vietmap.vn&sz=128",
            "fallback_logo": "/static/img/brands/vietmap.svg",
        },
    ]
    customer_highlights = [
        {
            "name": "Anh Minh",
            "role": "Chủ xe sedan",
            "quote": "Tư vấn đúng nhu cầu, lắp đặt gọn và sản phẩm dùng ổn định.",
        },
        {
            "name": "Chị Hương",
            "role": "Khách hàng thân thiết",
            "quote": "Mình quay lại nhiều lần vì chính sách bảo hành rõ ràng và hỗ trợ nhanh.",
        },
        {
            "name": "Garage AutoPro",
            "role": "Đối tác dịch vụ",
            "quote": "Nguồn hàng ổn định, phối hợp xử lý đơn và hậu mãi rất tốt.",
        },
    ]
    return {
        "news_posts": news_posts,
        "fallback_news": fallback_news,
        "partner_brands": partner_brands,
        "customer_highlights": customer_highlights,
    }


def _fallback_news_by_id():
    return {post["id"]: post for post in _editorial_context()["fallback_news"]}


def _news_card_from_blog(post, index=0):
    tags = ("Chăm sóc xe", "Kinh nghiệm sử dụng", "Thông tin cửa hàng")
    return {
        "id": f"post-{post.id}",
        "title": post.title,
        "excerpt": post.content,
        "content": post.content,
        "tag": tags[index % len(tags)],
        "image": "https://images.unsplash.com/photo-1489824904134-891ab64532f1?auto=format&fit=crop&w=1200&q=80",
        "date": post.created_at,
        "author": post.author.get_full_name() or post.author.username if post.author else "ETEK Store",
        "url_id": str(post.id),
        "source": "blog",
        "source_pk": post.id,
    }


def _news_card_from_fallback(post):
    return {
        "id": post["id"],
        "title": post["title"],
        "excerpt": post["excerpt"],
        "content": post["excerpt"],
        "tag": post["tag"],
        "image": post["image"],
        "date": None,
        "author": "ETEK Blog",
        "url_id": post["id"],
        "source": "fallback",
        "source_pk": post["id"],
    }


def _news_cards():
    posts = list(Blog.objects.select_related("author").order_by("-created_at"))
    if posts:
        return [_news_card_from_blog(post, index) for index, post in enumerate(posts)]
    return [_news_card_from_fallback(post) for post in _editorial_context()["fallback_news"]]


def _storefront_context(request):
    product_count_filter = Q(products__is_active=True, products__category__status="visible")
    categories = _visible_categories().annotate(
        product_total=Count("products", filter=product_count_filter)
    ).filter(product_total__gt=0).order_by("name")
    child_categories = (
        _visible_categories().annotate(product_total=Count("products", filter=product_count_filter))
        .filter(product_total__gt=0)
        .order_by("name")
        .prefetch_related(
            Prefetch(
                "children",
                queryset=_visible_categories()
                .annotate(product_total=Count("products", filter=product_count_filter))
                .order_by("name"),
            )
        )
    )
    menu_categories = (
        _visible_categories().filter(parent__isnull=True)
        .annotate(product_total=Count("products", filter=product_count_filter))
        .filter(product_total__gt=0)
        .order_by("name")
        .prefetch_related(Prefetch("children", queryset=child_categories))
    )
    featured_products = (
        _active_products()
        .order_by("-created_at")[:8]
    )
    context = {
        "nav_categories": categories,
        "menu_categories": menu_categories,
        "featured_products": featured_products,
    }
    context.update(_cart_summary(request))
    return context


def home(request):
    context = _storefront_context(request)
    best_sellers = list(
        _active_products()
        .annotate(sold_total=Coalesce(Sum("orderitem__quantity"), 0))
        .order_by("-sold_total", "-created_at")[:4]
    )
    if not any(product.sold_total for product in best_sellers):
        best_sellers = list(context["featured_products"][:4])

    context.update(_editorial_context())
    context["news_cards"] = _news_cards()[:3]
    context.update(
        {
            "hero_products": _active_products().order_by("-created_at")[:4],
            "category_spotlights": context["nav_categories"].order_by("-product_total", "name")[:4],
            "new_arrivals": _active_products().order_by("-created_at")[:4],
            "best_sellers": best_sellers,
            "deal_products": _active_products().order_by("price")[:4],
        }
    )
    return render(request, "store/home.html", context)


def news_list(request):
    context = _storefront_context(request)
    context.update(_editorial_context())
    context["news_cards"] = _news_cards()
    return render(request, "store/news_list.html", context)


def news_detail(request, identifier):
    context = _storefront_context(request)
    cards = _news_cards()

    article = None
    if identifier.isdigit():
        post = get_object_or_404(Blog.objects.select_related("author"), pk=int(identifier))
        article = _news_card_from_blog(post)
    else:
        fallback_post = _fallback_news_by_id().get(identifier)
        if not fallback_post:
            raise Http404("News article not found")
        article = _news_card_from_fallback(fallback_post)

    related_articles = [card for card in cards if card["url_id"] != article["url_id"]][:3]
    if not related_articles:
        related_articles = cards[:3]

    context.update(
        {
            "article": article,
            "related_articles": related_articles,
        }
    )
    return render(request, "store/news_detail.html", context)


def contact(request):
    context = _storefront_context(request)
    if request.method == "POST":
        name = request.POST.get("name", "").strip() or "khách hàng"
        messages.success(
            request,
            f"ETEK Store đã ghi nhận yêu cầu của {name}. Đội ngũ tư vấn sẽ liên hệ lại sớm.",
        )
        return redirect("store:contact")
    return render(request, "store/contact.html", context)


def product_list(request):
    context = _storefront_context(request)
    products = _active_products()
    categories = context["nav_categories"]

    selected_category = request.GET.get("category", "").strip()
    query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "latest").strip()

    if selected_category:
        products = products.filter(
            Q(category__slug=selected_category)
            | Q(category__parent__slug=selected_category)
            | Q(category__parent__parent__slug=selected_category)
        )

    search_context = None
    if query:
        products, search_context = search_products(products, query)

    if query:
        if sort == "price_asc":
            products = sorted(products, key=lambda product: (product.price, product.name.lower()))
        elif sort == "price_desc":
            products = sorted(products, key=lambda product: (-product.price, product.name.lower()))
        elif sort == "name":
            products = sorted(products, key=lambda product: product.name.lower())
    else:
        if sort == "price_asc":
            products = products.order_by("price", "-created_at")
        elif sort == "price_desc":
            products = products.order_by("-price", "-created_at")
        elif sort == "name":
            products = products.order_by("name")
        else:
            products = products.order_by("-created_at")

    paginator = Paginator(products, 9)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_query = request.GET.copy()
    page_query.pop("page", None)

    context.update(
        {
            "products": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "page_query": page_query.urlencode(),
            "categories": categories,
            "selected_category": selected_category,
            "query": query,
            "sort": sort,
            "total_products": paginator.count,
            "search_context": search_context,
        }
    )
    return render(request, "store/product_list.html", context)


def product_detail(request, pk):
    context = _storefront_context(request)
    product = get_object_or_404(
        _active_products(),
        pk=pk,
    )
    related_products = (
        _active_products()
        .filter(category=product.category)
        .exclude(pk=product.pk)
        .order_by("-created_at")[:4]
    )
    context.update(
        {
            "product": product,
            "related_products": related_products,
        }
    )
    return render(request, "store/product_detail.html", context)


def add_to_cart(request, pk):
    if request.method != "POST":
        return redirect("store:product_detail", pk=pk)

    product = get_object_or_404(_active_products(), pk=pk)
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    quantity = max(1, min(quantity, 99))

    cart = _get_current_cart(request, create=True)
    _upsert_cart_item(cart, product, quantity)

    if request.user.is_authenticated:
        RecommendationLog.objects.create(
            user=request.user,
            product=product,
            interaction_type="add_to_cart",
        )

    success_message = f"Đã thêm {quantity} x {product.name} vào giỏ hàng."
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        summary = _cart_summary(request)
        return JsonResponse(
            {
                "ok": True,
                "message": success_message,
                "cart_item_count": summary["cart_item_count"],
                "cart_total": str(summary["cart_total"]),
            }
        )

    messages.success(request, success_message)
    next_url = request.POST.get("next") or reverse("store:cart_detail")
    return redirect(next_url)


def cart_detail(request):
    context = _storefront_context(request)
    cart = context["cart"]
    cart_items = []
    if cart:
        for item in cart.items.select_related("product", "product__category").order_by("id"):
            cart_items.append(
                {
                    "item": item,
                    "line_total": item.product.price * item.quantity,
                }
            )
    context["cart_items"] = cart_items
    return render(request, "store/cart_detail.html", context)


def update_cart_item(request, item_id):
    if request.method != "POST":
        return redirect("store:cart_detail")

    item = _get_cart_item_or_404(request, item_id)
    action = request.POST.get("action", "set")

    if action == "increase":
        quantity = item.quantity + 1
    elif action == "decrease":
        quantity = item.quantity - 1
    else:
        try:
            quantity = int(request.POST.get("quantity", item.quantity))
        except (TypeError, ValueError):
            quantity = item.quantity

    if quantity <= 0:
        product_name = item.product.name
        item.delete()
        messages.success(request, f"Đã gỡ {product_name} khỏi giỏ hàng.")
        return redirect("store:cart_detail")

    item.quantity = max(1, min(quantity, 99))
    item.save(update_fields=["quantity"])
    messages.success(request, f"Đã cập nhật số lượng {item.product.name}.")
    return redirect("store:cart_detail")


def remove_cart_item(request, item_id):
    if request.method != "POST":
        return redirect("store:cart_detail")

    item = _get_cart_item_or_404(request, item_id)
    product_name = item.product.name
    item.delete()
    messages.success(request, f"Đã gỡ {product_name} khỏi giỏ hàng.")
    return redirect("store:cart_detail")
