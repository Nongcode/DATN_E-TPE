from django.core.management.base import BaseCommand, CommandError

from store.background_tasks import run_all_tasks, run_due_scheduled_tasks, run_task_type


class Command(BaseCommand):
    help = "Run ETEK background jobs for stock alerts, auto-hide, birthday care email, or due ScheduledTask rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--task",
            choices=["all", "due", "low-stock", "auto-hide", "birthday"],
            default="due",
            help="Task to run. Default is due, which executes pending ScheduledTask rows whose run_at has passed.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview task results without changing products, vouchers, or ScheduledTask statuses.",
        )

    def handle(self, *args, **options):
        task = options["task"]
        dry_run = options["dry_run"]

        try:
            if task == "due":
                results = run_due_scheduled_tasks(dry_run=dry_run)
            elif task == "all":
                results = run_all_tasks(dry_run=dry_run)
            else:
                task_map = {
                    "low-stock": "low_stock",
                    "auto-hide": "auto_hide",
                    "birthday": "birthday_mail",
                }
                results = [run_task_type(task_map[task], dry_run=dry_run)]
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        if not results:
            self.stdout.write(self.style.WARNING("No background tasks were executed."))
            return

        for result in results:
            self.stdout.write(result.as_log())

        self.stdout.write(self.style.SUCCESS("Background task execution completed."))
