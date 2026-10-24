"""Create or update the local development environment file.

The script never overwrites credentials that are already usable, so it can be
run again after a pull without invalidating the local administrator password.
"""

from __future__ import annotations

import contextlib
import secrets
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[1]
ENV_FILE: Path = ROOT / ".env"
EXAMPLE_FILE: Path = ROOT / ".env.example"

PASSWORD_PLACEHOLDER: str = "CHANGE_ME"
PASSWORD_BYTES: int = 18
SECRET_BYTES: int = 48
SECRET_MIN_LENGTH: int = 32
DEFAULT_USERNAME: str = "admin"


def read_values(lines: list[str]) -> dict[str, str]:
    """Return the key/value pairs of an environment file."""

    values: dict[str, str] = {}
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key] = value
    return values


def generate_secrets(values: dict[str, str]) -> dict[str, str]:
    """Return the secrets that have to be created or replaced."""

    generated: dict[str, str] = {}
    password = values.get("LOCAL_ADMIN_PASSWORD", "")
    if not password or password.startswith(PASSWORD_PLACEHOLDER):
        generated["LOCAL_ADMIN_PASSWORD"] = secrets.token_urlsafe(PASSWORD_BYTES)
    secret = values.get("LOCAL_SESSION_SECRET", "")
    if not secret or len(secret) < SECRET_MIN_LENGTH:
        generated["LOCAL_SESSION_SECRET"] = secrets.token_urlsafe(SECRET_BYTES)
    return generated


def apply_secrets(lines: list[str], generated: dict[str, str]) -> list[str]:
    """Return the environment file content with the generated secrets applied."""

    updated: list[str] = []
    replaced: set[str] = set()
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0]
            if key in generated:
                line = f"{key}={generated[key]}"
                replaced.add(key)
        updated.append(line)
    for key, value in generated.items():
        if key not in replaced:
            updated.append(f"{key}={value}")
    return updated


def main() -> None:
    """Create the local environment file and print the generated credentials."""

    if not ENV_FILE.exists():
        ENV_FILE.write_text(EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    generated = generate_secrets(read_values(lines))
    if generated:
        ENV_FILE.write_text("\n".join(apply_secrets(lines, generated)) + "\n", encoding="utf-8")
    with contextlib.suppress(OSError):
        ENV_FILE.chmod(0o600)
    values = read_values(ENV_FILE.read_text(encoding="utf-8").splitlines())
    username = values.get("LOCAL_ADMIN_USERNAME") or DEFAULT_USERNAME
    print(f"Local admin username: {username}")
    if "LOCAL_ADMIN_PASSWORD" in generated:
        print(f"One-time local admin password (also saved in .env): {generated['LOCAL_ADMIN_PASSWORD']}")
    else:
        print("The existing LOCAL_ADMIN_PASSWORD in .env will be used.")
    print("Local settings are stored in the ignored .env file.")


if __name__ == "__main__":
    main()
