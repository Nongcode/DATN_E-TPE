from decimal import Decimal
import re

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
        "dung cu sua chua garage": 54,
        "thiet bi lop": 42,
        "dung cu hoi": 40,
        "thiet bi nang ha": 30,
        "tu dung cu luu tru": 12,
    },
    "thiet bi lop": {
        "dung cu sua chua garage": 50,
        "dung cu hoi": 42,
        "thiet bi nang ha": 30,
        "thiet bi lop nang ha": 28,
    },
    "thiet bi nang ha": {
        "dung cu sua chua garage": 34,
        "thiet bi lop": 24,
        "tu dung cu luu tru": 18,
    },
    "rua xe detailing dong son": {
        "dung dich suc rua": 48,
        "may rua xe cham soc xe": 36,
        "thiet bi dong son": 24,
        "dung cu sua chua garage": 12,
    },
    "may rua xe cham soc xe": {
        "dung dich suc rua": 42,
        "rua xe detailing dong son": 34,
        "thiet bi dong son": 18,
    },
    "dung dich suc rua": {
        "rua xe detailing dong son": 44,
        "may rua xe cham soc xe": 34,
        "dung cu sua chua garage": 10,
    },
    "dung cu sua chua garage": {
        "dung cu hoi": 36,
        "thiet bi lop nang ha": 28,
        "thiet bi nang ha": 22,
        "tu dung cu luu tru": 20,
        "dung dich suc rua": 12,
    },
    "dung cu hoi": {
        "dung cu sua chua garage": 38,
        "thiet bi lop": 30,
        "thiet bi lop nang ha": 28,
    },
    "camera hanh trinh": {
        "cam bien oto": 36,
        "man hinh android": 30,
        "den oto": 18,
        "dung cu sua chua garage": 14,
    },
    "cam bien oto": {
        "camera hanh trinh": 28,
        "man hinh android": 24,
        "dung cu sua chua garage": 14,
    },
    "man hinh android": {
        "camera hanh trinh": 26,
        "cam bien oto": 24,
        "am thanh oto": 18,
    },
    "den oto": {
        "dung dich suc rua": 22,
        "dung cu sua chua garage": 14,
    },
}


COMPLEMENTARY_KEYWORD_RULES = {
    "lop": {"sung", "bom", "van", "oc", "khi", "nen", "co", "le", "kich", "nang", "ap", "suat", "tpms"},
    "lazang": {"wax", "ve", "sinh", "hoa", "chat", "rua", "detailing"},
    "nang": {"kich", "co", "le", "chan", "ke", "sua", "chua", "sung", "oc"},
    "rua": {"bot", "tuyet", "sung", "phun", "hut", "bui", "dung", "dich", "khan", "wax"},
    "son": {"phun", "say", "danh", "bong", "wax", "detailing", "dung", "dich"},
    "kinh": {"ve", "sinh", "dung", "dich", "khan", "gat", "mua"},
    "noi": {"that", "da", "ve", "sinh", "hut", "bui", "duong"},
    "kim": {"dung", "dich", "ve", "sinh", "buong", "dot"},
    "obd2": {"ac", "quy", "dien", "may", "phat", "camera", "noi", "soi", "kiem", "tra"},
    "camera": {"obd2", "ac", "quy", "may", "phat", "noi", "soi", "cam", "bien", "man", "hinh"},
    "ac": {"quy", "sac", "khoi", "dong", "kiem", "tra", "dien", "obd2"},
}


BUNDLE_USE_CASE_RULES = {
    "wheel_service": {
        "source": {"lop", "can", "bang", "nang", "lazang", "banh"},
        "candidate": {"sung", "bom", "van", "oc", "khi", "nen", "kich", "co", "le", "ap", "suat", "tpms", "dau"},
        "score": 34,
    },
    "battery_electrical": {
        "source": {"ac", "quy", "dien", "obd2", "camera", "cam", "bien", "den"},
        "candidate": {"obd2", "sac", "khoi", "dong", "kiem", "tra", "ac", "quy", "dien", "cam", "bien", "noi", "soi"},
        "score": 32,
    },
    "wash_detailing": {
        "source": {"rua", "detailing", "son", "wax", "kinh", "noi", "that", "da", "lazang"},
        "candidate": {"hoa", "chat", "dung", "dich", "wax", "ve", "sinh", "hut", "bui", "phun", "bot", "tuyet", "khan"},
        "score": 38,
    },
    "garage_setup": {
        "source": {"garage", "sua", "chua", "nang", "tu", "dung", "cu"},
        "candidate": {"tu", "dung", "cu", "sung", "co", "le", "kich", "chan", "ke", "obd2", "kiem", "tra"},
        "score": 28,
    },
    "driver_assist": {
        "source": {"camera", "cam", "bien", "man", "hinh", "android", "den"},
        "candidate": {"cam", "bien", "camera", "man", "hinh", "den", "obd2", "noi", "soi"},
        "score": 26,
    },
}


TIRE_SERVICE_CATEGORIES = {
    "thiet bi lop nang ha",
    "thiet bi lop",
    "thiet bi nang ha",
}

DETAILING_CATEGORIES = {
    "rua xe detailing dong son",
    "may rua xe cham soc xe",
    "dung dich suc rua",
    "thiet bi dong son",
}

DIRECT_TIRE_BUNDLE_TOKENS = {
    "lop",
    "sung",
    "bom",
    "van",
    "oc",
    "khi",
    "nen",
    "kich",
    "tpms",
    "dau",
    "banh",
    "me",
    "ke",
    "chan",
}

BUNDLE_RULE_GROUPS_BY_CATEGORY = {
    "thiet bi lop nang ha": {"wheel_service"},
    "thiet bi lop": {"wheel_service"},
    "thiet bi nang ha": {"wheel_service"},
    "rua xe detailing dong son": {"wash_detailing"},
    "may rua xe cham soc xe": {"wash_detailing"},
    "dung dich suc rua": {"wash_detailing"},
    "camera hanh trinh": {"driver_assist", "battery_electrical"},
    "cam bien oto": {"driver_assist", "battery_electrical"},
    "man hinh android": {"driver_assist"},
    "dung cu sua chua garage": {"wheel_service", "garage_setup", "battery_electrical"},
    "dung cu hoi": {"wheel_service", "garage_setup"},
}

GENERIC_CAR_BRANDS = {"toyota", "honda", "hyundai", "kia", "mazda", "ford"}
GENERIC_CAR_MODELS = {"vios", "city", "accent", "cerato", "mazda 3", "ranger"}

BUNDLE_ACCESSORY_TOKENS = {
    "bo",
    "sung",
    "van",
    "oc",
    "co",
    "le",
    "kich",
    "cam",
    "bien",
    "obd2",
    "ac",
    "quy",
    "sac",
    "dung",
    "dich",
    "hoa",
    "chat",
    "wax",
    "ve",
    "sinh",
    "hut",
    "bui",
    "khan",
    "tu",
    "phu",
    "kien",
}


METADATA_SPLIT_PATTERN = re.compile(r"[,;/|\n]+")


def metadata_values(value):
    if not value:
        return set()

    values = set()
    for item in METADATA_SPLIT_PATTERN.split(str(value)):
        normalized = normalize_text(item).strip()
        if normalized and normalized not in STOP_TOKENS:
            values.add(normalized)
    return values


def normalized_field(product, field_name):
    return normalize_text(getattr(product, field_name, "") or "").strip()


def vehicle_metadata(product):
    return {
        "car_brands": metadata_values(getattr(product, "compatible_car_brands", "")),
        "car_models": metadata_values(getattr(product, "compatible_car_models", "")),
    }


def product_tokens(product):
    category = product.category
    parent = category.parent if category else None
    fields = [
        product.name,
        product.sku,
        getattr(product, "brand", ""),
        getattr(product, "manufacturer", ""),
        getattr(product, "compatible_car_brands", ""),
        getattr(product, "compatible_car_models", ""),
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


def product_identity_tokens(product):
    category = product.category
    parent = category.parent if category else None
    fields = [
        product.name,
        product.sku,
        product.slug,
        category.name if category else "",
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


def structured_metadata_score(source, candidate):
    score = 0
    source_vehicle = vehicle_metadata(source)
    candidate_vehicle = vehicle_metadata(candidate)

    if source_vehicle["car_models"] and candidate_vehicle["car_models"]:
        score += len(source_vehicle["car_models"] & candidate_vehicle["car_models"]) * 80

    if source_vehicle["car_brands"] and candidate_vehicle["car_brands"]:
        score += len(source_vehicle["car_brands"] & candidate_vehicle["car_brands"]) * 54

    source_brand = normalized_field(source, "brand")
    candidate_brand = normalized_field(candidate, "brand")
    if source_brand and source_brand == candidate_brand:
        score += 32

    source_manufacturer = normalized_field(source, "manufacturer")
    candidate_manufacturer = normalized_field(candidate, "manufacturer")
    if source_manufacturer and source_manufacturer == candidate_manufacturer:
        score += 24

    return score


def score_similar_product(source, candidate):
    source_tokens = product_tokens(source)
    candidate_tokens = product_tokens(candidate)
    score = structured_metadata_score(source, candidate)
    score += content_overlap_score(source_tokens, candidate_tokens)

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


def complementary_keyword_score(source_tokens, candidate_tokens, source_category=""):
    score = 0
    for source_token, target_tokens in COMPLEMENTARY_KEYWORD_RULES.items():
        if source_category in TIRE_SERVICE_CATEGORIES and source_token in {"lazang", "rua", "son", "kinh", "noi"}:
            continue
        if source_token in source_tokens:
            overlap = candidate_tokens & target_tokens
            if overlap:
                score += 10 + min(len(overlap) * 5, 18)
    return score


def allowed_bundle_rule_names(source_category):
    return BUNDLE_RULE_GROUPS_BY_CATEGORY.get(source_category, set(BUNDLE_USE_CASE_RULES))


def bundle_use_case_score(source_tokens, candidate_tokens, source_category=""):
    score = 0
    allowed_rules = allowed_bundle_rule_names(source_category)
    for name, rule in BUNDLE_USE_CASE_RULES.items():
        if name not in allowed_rules:
            continue
        source_overlap = source_tokens & rule["source"]
        candidate_overlap = candidate_tokens & rule["candidate"]
        if source_overlap and candidate_overlap:
            score += rule["score"]
            score += min((len(source_overlap) + len(candidate_overlap)) * 3, 18)
    return score


def has_generic_vehicle_metadata(product):
    metadata = vehicle_metadata(product)
    car_brands = metadata["car_brands"]
    car_models = metadata["car_models"]
    return (
        len(car_brands & GENERIC_CAR_BRANDS) >= 5
        and len(car_models & GENERIC_CAR_MODELS) >= 5
    )


def bundle_vehicle_context_score(source, candidate):
    if has_generic_vehicle_metadata(source) or has_generic_vehicle_metadata(candidate):
        return 0
    return min(structured_metadata_score(source, candidate), 32)


def bundle_accessory_score(candidate_tokens):
    overlap = candidate_tokens & BUNDLE_ACCESSORY_TOKENS
    if not overlap:
        return 0
    return 8 + min(len(overlap) * 3, 18)


def bundle_price_fit_score(source, candidate):
    if not source.price or not candidate.price:
        return 0

    source_price = Decimal(source.price)
    candidate_price = Decimal(candidate.price)
    if source_price <= 0 or candidate_price <= 0:
        return 0

    ratio = candidate_price / source_price
    if ratio <= Decimal("0.20"):
        return 24
    if ratio <= Decimal("0.45"):
        return 18
    if ratio <= Decimal("0.80"):
        return 12
    if ratio <= Decimal("1.15"):
        return 6
    if ratio >= Decimal("2.5"):
        return -8
    return 0


def same_category_bundle_adjustment(source, candidate, source_tokens, candidate_tokens):
    if not source.category_id or source.category_id != candidate.category_id:
        return 0

    if bundle_use_case_score(source_tokens, candidate_tokens, category_key(source)) > 0:
        return 8
    return -14


def score_bundle_product(source, candidate):
    source_tokens = product_tokens(source)
    candidate_tokens = product_tokens(candidate)
    source_category = category_key(source)
    candidate_category = category_key(candidate)

    if source_category in TIRE_SERVICE_CATEGORIES:
        candidate_identity_tokens = product_identity_tokens(candidate)
        has_direct_tire_signal = bool(candidate_identity_tokens & DIRECT_TIRE_BUNDLE_TOKENS)
        is_tire_equipment_category = candidate_category in TIRE_SERVICE_CATEGORIES
        if not has_direct_tire_signal and not is_tire_equipment_category:
            return 0

    category_score = COMPLEMENTARY_CATEGORY_RULES.get(source_category, {}).get(candidate_category, 0)
    use_case_score = bundle_use_case_score(source_tokens, candidate_tokens, source_category)
    keyword_score = complementary_keyword_score(source_tokens, candidate_tokens, source_category)
    vehicle_score = bundle_vehicle_context_score(source, candidate)
    accessory_score = bundle_accessory_score(candidate_tokens)
    price_score = bundle_price_fit_score(source, candidate)
    content_score = min(content_overlap_score(source_tokens, candidate_tokens), 14)
    same_category_score = same_category_bundle_adjustment(
        source,
        candidate,
        source_tokens,
        candidate_tokens,
    )
    if source_category in TIRE_SERVICE_CATEGORIES and candidate_category in DETAILING_CATEGORIES:
        category_score -= 28
        keyword_score = min(keyword_score, 8)
        use_case_score = 0
    if source_category in TIRE_SERVICE_CATEGORIES and candidate_category in {
        "dung cu sua chua garage",
        "dung cu hoi",
        "thiet bi lop",
        "thiet bi nang ha",
    }:
        category_score += 18

    score = 0
    score += category_score
    score += use_case_score
    score += keyword_score
    score += vehicle_score
    score += accessory_score
    score += price_score
    score += content_score
    score += same_category_score

    if same_sku_family(source, candidate):
        score -= 6

    has_bundle_signal = any(
        [
            category_score,
            use_case_score,
            keyword_score,
            vehicle_score,
        ]
    )
    if not has_bundle_signal:
        return 0

    return max(score, 0)


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
