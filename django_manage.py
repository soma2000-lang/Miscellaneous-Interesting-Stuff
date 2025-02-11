import sys
from pathlib import Path

import django
from django import apps, conf
from django.utils.text import slugify

BASE_DIR = Path("").resolve()
APP_NAME = Path(__file__).parent.name


class AppConfig(apps.AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = APP_NAME


if not conf.settings.configured:
    conf.settings.configure(
        INSTALLED_APPS=[
            f"{APP_NAME}.django_manage.AppConfig",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / f"db_{slugify(APP_NAME)}.sqlite3",
                "OPTIONS": {
                    "init_command": (
                        "PRAGMA journal_mode = WAL;"
                        "PRAGMA synchronous = NORMAL;"
                        "PRAGMA busy_timeout = 5000;"
                        "PRAGMA temp_store = MEMORY;"
                        "PRAGMA mmap_size = 134217728;"
                        "PRAGMA journal_size_limit = 67108864;"
                        "PRAGMA cache_size = 2000;"
                    ),
                    "transaction_mode": "IMMEDIATE",
                },
            }
        },
        TIME_ZONE="Europe/Lisbon",
    )
    django.setup()


def main():
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
