from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


RECURRING_MINUTES_PREFIX = "recurring_minutes="


def update_inventory_thresholds(apps, schema_editor):
    Inventory = apps.get_model("store", "Inventory")
    Inventory.objects.update(low_stock_threshold=20)


def update_default_task_intervals(apps, schema_editor):
    ScheduledTask = apps.get_model("store", "ScheduledTask")
    local_now = timezone.localtime()
    task_configs = {
        "lock_stock": (360, "Canh bao ton kho thap"),
        "auto_hide": (5, "Tu dong an san pham het hang"),
    }
    for task_type, (interval_minutes, label) in task_configs.items():
        run_at = (local_now + timedelta(minutes=interval_minutes)).replace(second=0, microsecond=0)
        ScheduledTask.objects.filter(task_type=task_type, status="pending").update(
            run_at=run_at,
            execution_log=(
                f"{RECURRING_MINUTES_PREFIX}{interval_minutes}; "
                f"default_task=true; "
                f"next_run_at={timezone.localtime(run_at):%d/%m/%Y %H:%M}; "
                f"label={label}"
            ),
        )


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0006_merge_duplicate_categories_unique_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="inventory",
            name="low_stock_threshold",
            field=models.IntegerField(default=20, verbose_name="Ngưỡng cảnh báo (Mặc định: 20)"),
        ),
        migrations.RunPython(update_inventory_thresholds, migrations.RunPython.noop),
        migrations.RunPython(update_default_task_intervals, migrations.RunPython.noop),
    ]
