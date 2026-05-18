from decimal import Decimal

from django.db.models import QuerySet

from .search import normalize_text, tokenize_query


STOP_TOKENS = {
    "uptek",
    "etek",
    "may",
    "bo",
    "dung",
    "cu",
    "thiet",
    "bi",
    "san",
    "pham",
    "oto",
    "xe",
    "va",
    "cho",
    "theo",
    "trong",
    "voi",
    "inch",
}


COMPLEMENTARY_CATEGORY_RULES = {
    "thiet bi lop nang ha": {
        "dung cu sua chua garage": 34,
        "rua xe detailing dong son": 18,
    },
    "rua xe detailing dong son": {
        "dung dich suc rua": 38,
        "dung cu sua chua garage": 16,
    },
    "dung dich suc rua": {
        "rua xe detailing dong son": 38,
        "dung cu sua chua garage": 16,
    },
    "dung cu sua chua garage": {
        "thiet bi lop nang ha": 24,
        "rua xe detailing dong son": 18,
        "dung dich suc rua": 12,
    },
    "camera hanh trinh": {
        "dung cu sua chua garage": 18,
        "cam bien oto": 16,
    },
}


COMPLEMENTARY_KEYWORD_RULES = {
    "lop": {"sung", "khi", "nen", "co", "le", "kich", "nang", "obd2"},
    "nang": {"kich", "co", "le", "chan", "doan", "sua", "chua"},
    "rua": {"bot", "tuyet", "sung", "phun", "hut", "bui", "dung", "dich"},
    "son": {"phun", "say", "danh", "bong", "detailing"},
    "kim": {"dung", "dich", "ve", "sinh", "buong", "dot"},
    "obd2": {"ac", "quy", "may", "phat", "camera", "noi", "soi"},
    "camera": {"obd2", "ac", "quy", "may", "phat", "noi", "soi", "cam", "bien"},
}


def product_tokens(product):
    category = product.category
    parent = category.parent if category else None
    fields = [
        product.name,
        product.sku,
        product.description,
        product.slug,
        category.name if category else "",
        category.description if category else "",
        parent.name if parent else "",
    ]
    tokens = set()
    for field in fields:
        tokens.update(tokenize_query(field))
    return {token for token in tokens if token not in STOP_TOKENS}


def category_key(product):
    if not product.category:
        return ""
    return normalize_text(product.category.name)


def price_similarity_score(source, candidate):
    if not source.price or not candidate.price:
        return 0
    source_price = Decimal(source.price)
    candidate_price = Decimal(candidate.price)
    if source_price <= 0 or candidate_price <= 0:
        return 0
    ratio = abs(source_price - candidate_price) / max(source_price, candidate_price)
    if ratio <= Decimal("0.15"):
        return 18
    if ratio <= Decimal("0.35"):
        return 10
    if ratio <= Decimal("0.6"):
        return 4
    return 0


def content_overlap_score(source_tokens, candidate_tokens):
    if not source_tokens or not candidate_tokens:
        return 0
    overlap = source_tokens & candidate_tokens
    coverage = len(overlap) / max(len(source_tokens), 1)
    return (len(overlap) * 8) + int(coverage * 24)


def same_sku_family(source, candidate):
    source_prefix = [token for token in normalize_text(source.sku or "").split() if token not in STOP_TOKENS]
    candidate_prefix = [token for token in normalize_text(candidate.sku or "").split() if token not in STOP_TOKENS]
    if not source_prefix or not candidate_prefix:
        return False
    return source_prefix[0] == candidate_prefix[0]


def score_similar_product(source, candidate):
    source_tokens = product_tokens(source)
    candidate_tokens = product_tokens(candidate)
    score = content_overlap_score(source_tokens, candidate_tokens)

    if source.category_id and source.category_id == candidate.category_id:
        score += 46
    elif category_key(source) == category_key(candidate):
        score += 34

    if score <= 0 and not same_sku_family(source, candidate):
        return 0

    score += price_similarity_score(source, candidate)

    if same_sku_family(source, candidate):
        score += 8

    return score


def complementary_keyword_score(source_tokens, candidate_tokens):
    score = 0
    for source_token, target_tokens in COMPLEMENTARY_KEYWORD_RULES.items():
        if source_token in source_tokens and candidate_tokens & target_tokens:
            score += 12
    return score


def score_bundle_product(source, candidate):
    source_tokens = product_tokens(source)
    candidate_tokens = product_tokens(candidate)
    source_category = category_key(source)
    candidate_category = category_key(candidate)

    score = 0
    score += COMPLEMENTARY_CATEGORY_RULES.get(source_category, {}).get(candidate_category, 0)
    score += complementary_keyword_score(source_tokens, candidate_tokens)

    if source.category_id and source.category_id == candidate.category_id:
        score += 8

    if candidate.price and source.price and Decimal(candidate.price) <= Decimal(source.price):
        score += 8

    score += min(content_overlap_score(source_tokens, candidate_tokens), 18)
    return score


def ranked_recommendations(product, products, scorer, limit=4, exclude_ids=None):
    if isinstance(products, QuerySet):
        products = list(products.select_related("category", "category__parent"))
    else:
        products = list(products)

    excluded = {product.pk}
    if exclude_ids:
        excluded.update(exclude_ids)

    ranked = []
    for candidate in products:
        if candidate.pk in excluded:
            continue
        score = scorer(product, candidate)
        if score <= 0:
            continue
        candidate.recommendation_score = score
        ranked.append(candidate)

    ranked.sort(key=lambda item: (-item.recommendation_score, item.name.lower(), item.pk))
    return ranked[:limit]


def get_similar_products(product, products, limit=4):
    return ranked_recommendations(product, products, score_similar_product, limit=limit)


def get_bundle_products(product, products, limit=4, exclude_ids=None):
    return ranked_recommendations(
        product,
        products,
        score_bundle_product,
        limit=limit,
        exclude_ids=exclude_ids,
    )
