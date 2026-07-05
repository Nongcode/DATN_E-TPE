from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from store.background_tasks import RECURRING_DAILY_MARKER, RECURRING_MINUTES_PREFIX
from store.models import ScheduledTask


DEFAULT_TASKS = (
    ("lock_stock", "Cảnh báo tồn kho thấp", 360),
    ("auto_hide", "Tự động ẩn sản phẩm hết hàng", 5),
    ("birthday_mail", "Gửi email chăm sóc sinh nhật", None),
)


class Command(BaseCommand):
    help = "Create default ScheduledTask rows so admins can see and run background jobs from Django Admin."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing pending default tasks before creating fresh rows.",
        )
        parser.add_argument(
            "--hour",
            type=int,
            default=8,
            help="Daily trigger hour in Django local timezone for daily tasks. Default: 8.",
        )
        parser.add_argument(
            "--minute",
            type=int,
            default=0,
            help="Daily trigger minute in Django local timezone for daily tasks. Default: 0.",
        )

    def handle(self, *args, **options):
        hour = max(0, min(options["hour"], 23))
        minute = max(0, min(options["minute"], 59))
        if options["reset"]:
            ScheduledTask.objects.filter(
                status="pending",
                task_type__in=[task_type for task_type, _, _ in DEFAULT_TASKS],
            ).delete()

        local_now = timezone.localtime()
        daily_run_at = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if daily_run_at <= local_now:
            daily_run_at += timedelta(days=1)

        created_count = 0
        skipped_count = 0

        for task_type, label, interval_minutes in DEFAULT_TASKS:
            exists = ScheduledTask.objects.filter(task_type=task_type, status="pending").exists()
            if exists:
                skipped_count += 1
                self.stdout.write(f"Skipped existing pending task: {label}")
                continue

            if interval_minutes:
                run_at = (local_now + timedelta(minutes=interval_minutes)).replace(second=0, microsecond=0)
                recurring_marker = f"{RECURRING_MINUTES_PREFIX}{interval_minutes}"
            else:
                run_at = daily_run_at
                recurring_marker = RECURRING_DAILY_MARKER

            ScheduledTask.objects.create(
                task_type=task_type,
                status="pending",
                run_at=run_at,
                execution_log=(
                    f"{recurring_marker}; "
                    f"default_task=true; "
                    f"next_run_at={timezone.localtime(run_at):%d/%m/%Y %H:%M}; "
                    f"label={label}"
                ),
            )
            created_count += 1
            self.stdout.write(f"Created default task: {label}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Default ScheduledTask seed completed. Created: {created_count}, skipped: {skipped_count}."
            )
        )
