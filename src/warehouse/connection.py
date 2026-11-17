"""Read local MySQL settings and open a connection without logging secrets."""

import re

import mysql.connector
from dotenv import dotenv_values

from src.ingestion.explore_dataset import ROOT


def mysql_settings(env_file=ROOT / ".env"):
    if not env_file.is_file():
        raise ValueError("Create .env from .env.example and fill in your local MySQL settings.")

    settings = dotenv_values(env_file, interpolate=False)
    required = ("DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if not settings.get(name)]
    if missing:
        raise ValueError("Set these values in the local .env file: " + ", ".join(missing))

    database = settings["DB_NAME"]
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", database):
        raise ValueError("DB_NAME must be at most 64 letters, digits, or underscores and start with a letter or underscore.")
    try:
        port = int(settings.get("DB_PORT") or 3306)
    except ValueError:
        raise ValueError("DB_PORT must be an integer from 1 to 65535.") from None
    if not 1 <= port <= 65535:
        raise ValueError("DB_PORT must be an integer from 1 to 65535.")

    return database, {
        "host": settings.get("DB_HOST") or "localhost",
        "port": port,
        "user": settings["DB_USER"],
        "password": settings["DB_PASSWORD"],
        "charset": "utf8mb4",
        "connection_timeout": 10,
        "autocommit": False,
    }


def connect_to_mysql(**settings):
    return mysql.connector.connect(**settings)
