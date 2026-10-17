"""The owner's service credentials, kept encrypted instead of in plain text.

Channel and connector credentials (TELEGRAM_BOT_TOKEN, X_API_SECRET,
XMPP_PASSWORD, NOSTR_SECRET, IMAP_PASSWORD, ...) could only be given as
environment variables, which in practice means a plain-text .env file
any program running as the owner can read. settings.toml refuses
secrets for the same reason. `python -m Agent_Guru vault set NAME` keeps
one here instead, through security/secret_store.py: on Windows encrypted
with DPAPI for the owner's account, so a copied file is useless on
another account or machine.

At start, apply() puts each stored value in the environment where the
variable is not already set: a variable set in the environment (or
.env) still wins, as it does over settings.toml. Values are never
printed; `vault list` shows names only.
"""

from __future__ import annotations

import os
import re

from Agent_Guru.security import secret_store

_SECRET_NAME = "vault"  # nosec B105 - the name of the store, not a secret
_NAME = re.compile(r"[A-Z][A-Z0-9_]{1,63}")
_MAX_VALUE = 8192


def _load() -> dict[str, str]:
    stored = secret_store.load_json(_SECRET_NAME)
    return {k: v for k, v in (stored or {}).items() if isinstance(k, str) and isinstance(v, str)}


def names() -> list[str]:
    return sorted(_load())


def put(name: str, value: str) -> None:
    if not _NAME.fullmatch(name):
        msg = "a name is an environment variable name: capital letters, digits and _"
        raise ValueError(msg)
    if not value or len(value) > _MAX_VALUE or "\n" in value or "\0" in value:
        msg = f"a value is one line of 1 to {_MAX_VALUE} characters"
        raise ValueError(msg)
    stored = _load()
    stored[name] = value
    secret_store.save_json(_SECRET_NAME, stored)


def remove(name: str) -> bool:
    stored = _load()
    if name not in stored:
        return False
    del stored[name]
    secret_store.save_json(_SECRET_NAME, stored)
    return True


def apply(environ: dict[str, str] | None = None) -> list[str]:
    """Fill unset variables from the vault; returns the names filled. Never raises."""
    target = os.environ if environ is None else environ
    try:
        stored = _load()
    except Exception as exc:
        # A vault made on another account or machine cannot be decrypted;
        # the assistant still starts, without those credentials.
        import logging

        logging.getLogger(__name__).warning("The credential vault could not be read: %s", type(exc).__name__)
        return []
    filled = []
    for name, value in stored.items():
        if not target.get(name):
            target[name] = value
            filled.append(name)
    return sorted(filled)


def run(argv: list[str]) -> int:
    import argparse
    import getpass
    import sys

    parser = argparse.ArgumentParser(
        prog="python -m Agent_Guru vault",
        description="Service credentials kept encrypted for this Windows account, not in a plain-text file.",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    set_ = sub.add_parser("set", help="store a credential (the value is asked for, not typed on the command line)")
    set_.add_argument("name")
    sub.add_parser("list", help="the names stored (never the values)")
    rm = sub.add_parser("remove", help="delete one")
    rm.add_argument("name")
    args = parser.parse_args(argv)
    if args.action == "list":
        for name in names():
            shadow = " (the environment's value is used instead)" if os.environ.get(name) else ""
            print(f"  {name}{shadow}")  # noqa: T201  the command's output
        return 0
    if args.action == "remove":
        found = remove(args.name)
        print(f"Removed {args.name}." if found else f"{args.name} is not stored.")  # noqa: T201
        return 0 if found else 1
    # Asked for, not an argument: a command line is kept in shell history
    # and visible to other programs while it runs.
    value = getpass.getpass(f"{args.name}: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\r\n")
    try:
        put(args.name, value)
    except ValueError as exc:
        print(f"Not stored: {exc}")  # noqa: T201
        return 1
    print(f"Stored {args.name}. It is used from the next start, unless the environment sets it.")  # noqa: T201
    return 0
