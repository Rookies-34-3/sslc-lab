"""Create private local settings without replacing an existing .env."""
import secrets
from pathlib import Path

destination = Path(__file__).resolve().parents[1] / ".env"
if destination.exists():
    print("Using existing .env.")
else:
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(
            "HOST_BIND=127.0.0.1\nHOST_PORT=8080\n"
            f"SECRET_KEY={secrets.token_hex(32)}\n"
            f"MYSQL_PASSWORD={secrets.token_hex(24)}\n"
            f"MYSQL_ROOT_PASSWORD={secrets.token_hex(32)}\n"
            "LAB_PASSWORD=Lab1234!\nCOOKIE_SECURE=false\n"
        )
    print("Created private .env for local preview.")
