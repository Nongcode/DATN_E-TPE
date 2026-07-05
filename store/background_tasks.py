from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Customer, Inventory, Product, ScheduledTask, Voucher


RECURRING_DAILY_MARKER = "recurring=daily"
RECURRING_MINUTES_PREFIX = "recurring_minutes="


@dataclass
class TaskResult:
    name: str
    processed: int = 0
    sent: int = 0
    skipped: int = 0
    updated: int = 0
    message: str = ""

    def as_log(self):
        parts = [
            f"task={self.name}",
            f"processed={self.processed}",
            f"sent={self.sent}",
            f"updated={self.updated}",
            f"skipped={self.skipped}",
        ]
        if self.message:
            parts.append(f"message={self.message}")
        return "; ".join(parts)


def is_recurring_daily_task(task):
    return bool(task.execution_log and RECURRING_DAILY_MARKER in task.execution_log)


def recurring_interval_minutes(task):
    if not task.execution_log:
        return None
    for part in task.execution_log.split(";"):
        part = part.strip()
        if not part.startswith(RECURRING_MINUTES_PREFIX):
            continue
        try:
            minutes = int(part.replace(RECURRING_MINUTES_PREFIX, "", 1))
        except ValueError:
            return None
        return minutes if minutes > 0 else None
    return None


def next_daily_run_at(run_at, now=None):
    now = timezone.localtime(now or timezone.now())
    candidate = timezone.localtime(run_at).replace(second=0, microsecond=0)
    while candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def next_interval_run_at(run_at, minutes, now=None):
    now = timezone.localtime(now or timezone.now())
    candidate = timezone.localtime(run_at).replace(second=0, microsecond=0)
    interval = timedelta(minutes=minutes)
    while candidate <= now:
        candidate += interval
    return candidate


def _configured_stock_recipients():
    configured = getattr(settings, "STOCK_ALERT_EMAILS", [])
    recipients = [email.strip() for email in configured if email and email.strip()]
    if recipients:
        return recipients

    return list(
        User.objects.filter(is_staff=True, email__isnull=False)
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )


def send_low_stock_alerts(dry_run=False):
    inventories = list(
        Inventory.objects.select_related("product", "product__category")
        .filter(product__is_active=True, quantity__gt=0, quantity__lte=F("low_stock_threshold"))
        .order_by("quantity", "product__name")
    )
    recipients = _configured_stock_recipients()

    if not inventories:
        return TaskResult("low_stock_alert", message="Không có sản phẩm sắp hết hàng.")

    lines = [
        "Xin chào quản trị viên,",
        "",
        "Hệ thống ETEK Store ghi nhận các sản phẩm sau đang có tồn kho thấp và cần được kiểm tra:",
        "",
    ]
    for item in inventories:
        lines.append(
            f"- {item.product.name} | SKU: {item.product.sku or 'Chưa có SKU'} | "
            f"Tồn kho hiện tại: {item.quantity} | Ngưỡng cảnh báo: {item.low_stock_threshold}"
        )

    lines.extend([
        "",
        "Vui lòng kiểm tra kho và bổ sung hàng nếu cần.",
        "",
        "Trân trọng,",
        "ETEK Store",
    ])

    if recipients and not dry_run:
        send_mail(
            subject="[ETEK] Cảnh báo tồn kho thấp",
            message="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )

    message = "Đã gửi email cảnh báo." if recipients and not dry_run else "Không gửi email trong chế độ chạy thử hoặc chưa có người nhận."
    return TaskResult(
        "low_stock_alert",
        processed=len(inventories),
        sent=1 if recipients and not dry_run else 0,
        skipped=0 if recipients else len(inventories),
        message=message,
    )


def hide_out_of_stock_products(dry_run=False):
    product_ids = list(
        Inventory.objects.filter(product__is_active=True, quantity__lte=0)
        .values_list("product_id", flat=True)
    )
    if not dry_run and product_ids:
        Product.objects.filter(pk__in=product_ids).update(is_active=False)

    return TaskResult(
        "auto_hide_out_of_stock",
        processed=len(product_ids),
        updated=0 if dry_run else len(product_ids),
        message="Ẩn sản phẩm có tồn kho <= 0." if product_ids else "Không có sản phẩm cần ẩn.",
    )


def send_birthday_care_emails(today=None, dry_run=False):
    now = timezone.now()
    today = today or timezone.localdate(now)
    customers = list(
        Customer.objects.select_related("user")
        .filter(date_of_birth__month=today.month, date_of_birth__day=today.day, email__isnull=False)
        .exclude(email="")
        .order_by("id")
    )

    discount_amount = Decimal(str(getattr(settings, "BIRTHDAY_VOUCHER_AMOUNT", "100000")))
    valid_until = now + timedelta(days=int(getattr(settings, "BIRTHDAY_VOUCHER_VALID_DAYS", 2)))
    sent_count = 0
    skipped_count = 0

    for customer in customers:
        code = f"BDAY{today:%Y%m%d}{customer.pk:05d}"
        voucher_exists = Voucher.objects.filter(code=code).exists()
        if voucher_exists:
            skipped_count += 1
            continue

        if dry_run:
            sent_count += 1
            continue

        voucher = Voucher.objects.create(
            code=code,
            customer=customer,
            discount_amount=discount_amount,
            valid_until=valid_until,
        )
        name = customer.full_name or customer.user.get_full_name() or customer.user.username
        discount_text = f"{voucher.discount_amount:,.0f}".replace(",", ".")
        valid_until_text = timezone.localtime(voucher.valid_until).strftime("%d/%m/%Y")
        send_mail(
            subject="ETEK Store chúc mừng sinh nhật anh/chị",
            message=(
                f"Xin chào {name},\n\n"
                "ETEK Store chúc anh/chị một ngày sinh nhật thật vui vẻ, nhiều sức khỏe và luôn gặp nhiều may mắn.\n\n"
                f"Nhân dịp sinh nhật, hệ thống gửi tặng anh/chị mã ưu đãi {voucher.code} trị giá {discount_text} đ. "
                f"Mã ưu đãi có hiệu lực đến hết ngày {valid_until_text}.\n\n"
                "Cảm ơn anh/chị đã tin tưởng và đồng hành cùng ETEK Store."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer.email],
            fail_silently=False,
        )
        sent_count += 1

    return TaskResult(
        "birthday_care_email",
        processed=len(customers),
        sent=sent_count,
        skipped=skipped_count,
        message=f"Ngày xử lý {today:%d/%m/%Y}.",
    )


def run_task_type(task_type, dry_run=False):
    if task_type in ("low_stock", "lock_stock"):
        return send_low_stock_alerts(dry_run=dry_run)
    if task_type in ("auto_hide", "auto_hide_out_of_stock"):
        return hide_out_of_stock_products(dry_run=dry_run)
    if task_type in ("birthday_mail", "birthday"):
        return send_birthday_care_emails(dry_run=dry_run)
    raise ValueError(f"Unsupported scheduled task type: {task_type}")


def run_all_tasks(dry_run=False):
    return [
        send_low_stock_alerts(dry_run=dry_run),
        hide_out_of_stock_products(dry_run=dry_run),
        send_birthday_care_emails(dry_run=dry_run),
    ]


def execute_scheduled_task(task, now=None, dry_run=False):
    now = now or timezone.now()
    try:
        result = run_task_type(task.task_type, dry_run=dry_run)
    except Exception as exc:
        if not dry_run:
            task.status = "failed"
            task.execution_log = str(exc)
            task.save(update_fields=["status", "execution_log"])
        return TaskResult(task.task_type, message=f"failed: {exc}")

    if not dry_run:
        interval_minutes = recurring_interval_minutes(task)
        if interval_minutes:
            next_run_at = next_interval_run_at(task.run_at, interval_minutes, now=now)
            task.status = "pending"
            task.run_at = next_run_at
            task.execution_log = (
                f"{RECURRING_MINUTES_PREFIX}{interval_minutes}; "
                f"last_run_at={timezone.localtime(now):%d/%m/%Y %H:%M}; "
                f"next_run_at={timezone.localtime(next_run_at):%d/%m/%Y %H:%M}; "
                f"{result.as_log()}"
            )
            task.save(update_fields=["status", "run_at", "execution_log"])
        elif is_recurring_daily_task(task):
            next_run_at = next_daily_run_at(task.run_at, now=now)
            task.status = "pending"
            task.run_at = next_run_at
            task.execution_log = (
                f"{RECURRING_DAILY_MARKER}; "
                f"last_run_at={timezone.localtime(now):%d/%m/%Y %H:%M}; "
                f"next_run_at={timezone.localtime(next_run_at):%d/%m/%Y %H:%M}; "
                f"{result.as_log()}"
            )
            task.save(update_fields=["status", "run_at", "execution_log"])
        else:
            task.status = "success"
            task.execution_log = result.as_log()
            task.save(update_fields=["status", "execution_log"])

    return result


def run_due_scheduled_tasks(now=None, dry_run=False):
    now = now or timezone.now()
    task_ids = list(
        ScheduledTask.objects.filter(status="pending", run_at__lte=now)
        .order_by("run_at", "id")
        .values_list("id", flat=True)
    )
    results = []

    for task_id in task_ids:
        with transaction.atomic():
            task = ScheduledTask.objects.select_for_update().get(pk=task_id)
            if task.status != "pending" or task.run_at > now:
                continue
            result = execute_scheduled_task(task, now=now, dry_run=dry_run)
            results.append(result)

    return results


