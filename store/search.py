import re
import unicodedata

from django.db.models import QuerySet


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def normalize_text(value):
    if value is None:
        return ""
    value = str(value).lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.replace("đ", "d")
    return " ".join(TOKEN_PATTERN.findall(value))


def tokenize_query(query):
    normalized = normalize_text(query)
    return [token for token in normalized.split() if len(token) >= 2]


def product_search_document(product):
    category = product.category
    parent = category.parent if category else None
    fields = {
        "name": product.name,
        "sku": product.sku,
        "description": product.description,
        "category": category.name if category else "",
        "category_description": category.description if category else "",
        "parent_category": parent.name if parent else "",
        "slug": product.slug,
    }
    normalized = {key: normalize_text(value) for key, value in fields.items()}
    normalized["all"] = " ".join(normalized.values())
    return normalized


def score_product(product, query):
    tokens = tokenize_query(query)
    if not tokens:
        return 0

    document = product_search_document(product)
    score = 0
    full_query = normalize_text(query)

    if full_query and full_query in document["name"]:
        score += 90
    if full_query and full_query in document["category"]:
        score += 55
    if full_query and full_query in document["sku"]:
        score += 80

    for token in tokens:
        if token in document["name"]:
            score += 28
        if token in document["sku"]:
            score += 32
        if token in document["category"]:
            score += 22
        if token in document["parent_category"]:
            score += 16
        if token in document["description"]:
            score += 12
        if token in document["category_description"]:
            score += 8
        if token in document["slug"]:
            score += 6

    matched_tokens = sum(1 for token in tokens if token in document["all"])
    if matched_tokens == len(tokens):
        score += 24
    elif matched_tokens:
        score += matched_tokens * 4

    return score


def required_token_matches(tokens):
    if len(tokens) <= 1:
        return len(tokens)
    if len(tokens) <= 3:
        return len(tokens)
    return len(tokens) - 1


def search_products(products, query):
    if isinstance(products, QuerySet):
        products = list(products.select_related("category", "category__parent"))
    else:
        products = list(products)

    tokens = tokenize_query(query)
    if not tokens:
        return products, {"query": query, "tokens": [], "matched_count": len(products)}

    scored_products = []
    for product in products:
        score = score_product(product, query)
        document = product_search_document(product)
        matched_tokens = sum(1 for token in tokens if token in document["all"])
        if score > 0 and matched_tokens >= required_token_matches(tokens):
            product.search_score = score
            scored_products.append(product)

    scored_products.sort(key=lambda product: (-product.search_score, product.name.lower(), product.pk))
    return scored_products, {
        "query": query,
        "tokens": tokens,
        "matched_count": len(scored_products),
    }
