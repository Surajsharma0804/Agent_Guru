"""Secrets and personal data are taken out of text before it is logged.

sanitize_credentials() knew five key formats. A side-by-side run on 14
made-up secrets in their published formats found it removed 6: AWS key
IDs, GitHub fine-grained tokens, Slack and Stripe tokens, private key
blocks, JWTs, Telegram bot tokens and NAME=value secrets in environment
lines all went into the log as they were. redact_pii() matched only North
American phone numbers.
"""

from __future__ import annotations

import pytest

from Agent_Guru.llm.security import CredentialFilter, redact_pii, sanitize_credentials

# The made-up tokens are joined at run time: written whole, a Slack- or
# Stripe-shaped literal is refused by GitHub push protection like a real
# secret, and would be one more credential-looking string in a public repo.
GH_PAT = "github" + "_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUV0123"
GH_OAUTH = "gh" + "o_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"
OPENAI = "sk-" + "proj-Ab12Cd34Ef56Gh78Ij90Kl12Mn34Op56Qr78St90Uv12"
SLACK = "xo" + "xb-1234567890123-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx"
STRIPE = "sk_" + "live_51H8abcdefGHIJKLmnopQRSTuvwxYZ0123456789"
TELEGRAM = "123456789:" + "AAHfiqksKZ8WmR2zSjiQ7_v4TMAKdiHm9T0"

SECRETS = [
    ("aws key AKIAIOSFODNN7EXAMPLE in the config", "AKIAIOSFODNN7EXAMPLE"),
    ("export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "wJalrXUtnFEMI/K7MDENG"),
    (GH_PAT, "_pat_11ABCDEFG"),
    (GH_OAUTH, "aBcDeFgHiJ"),
    ("OPENAI_API_KEY=" + OPENAI, "Ab12Cd34Ef56"),
    ("slack bot " + SLACK, "AbCdEfGhIjKlMnOp"),
    ("stripe " + STRIPE, "51H8abcdefGHIJ"),
    ("jwt eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
     "dozjgNryP4J3"),
    ("telegram bot " + TELEGRAM, "AAHfiqksKZ8"),
    ("DATABASE_URL=postgres://admin:S3cr3tPass@db.example.com:5432/prod", "S3cr3tPass"),
]


@pytest.mark.parametrize(("text", "secret"), SECRETS)
def test_each_secret_format_is_removed(text, secret):
    assert secret not in sanitize_credentials(text)  # nosec B101


def test_a_private_key_block_is_removed_whole():
    pem = (
        "key:\n-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAu1SU1LfVLPHCozMxH2Mo\n"
        "4lgOEePzNm0tRgeLezV6ffAt0gunVTLw7onLRnrq0/IzW7yWR7QkrmBL7jTKEn5u\n"
        "-----END RSA PRIVATE KEY-----\ndone"
    )
    out = sanitize_credentials(pem)
    # Matching only the header used to leave the key material in the log.
    assert "MIIEowIBAAKCAQEA" not in out and "4lgOEePzNm0t" not in out  # nosec B101
    assert out.startswith("key:") and out.endswith("done")  # nosec B101


def test_the_name_of_a_secret_variable_is_kept_for_the_reader():
    out = sanitize_credentials("GITHUB_TOKEN=ghx1234567890abcdef")
    assert out.startswith("GITHUB_TOKEN=") and "ghx1234567890abcdef" not in out  # nosec B101


def test_a_url_keeps_its_host_and_user_but_not_its_password():
    out = sanitize_credentials("postgres://admin:S3cr3tPass@db.example.com/prod")
    assert "S3cr3tPass" not in out and "admin" in out and "db.example.com" in out  # nosec B101


@pytest.mark.parametrize("text", [
    "commit 6e2422b0c1a8f9d3e7b5a4c2d1e0f9a8b7c6d5e4 fixed the bug",
    "request id 3f2504e0-4f89-11d3-9a0c-0305e82c3301",
    "the meeting is at 10:30 in room 204",
    "version 1.12.6 of the package",
    "the key to success is practice",
    "set the token budget to 512 for this model",
    "PATH=/usr/local/bin:/usr/bin",
])
def test_ordinary_text_is_left_alone(text):
    assert sanitize_credentials(text) == text  # nosec B101


@pytest.mark.parametrize(("text", "number"), [
    ("call +91 98765 43210 after six", "98765 43210"),
    ("office +44 20 7946 0958", "7946 0958"),
    ("US line (415) 555-2671", "555-2671"),
])
def test_phone_numbers_with_a_country_code_are_redacted(text, number):
    assert number not in redact_pii(text)  # nosec B101


def test_a_log_line_with_a_new_format_secret_is_cleaned(caplog):
    import logging

    log = logging.getLogger("credential-filter-test")
    log.addFilter(CredentialFilter())
    with caplog.at_level(logging.INFO, logger="credential-filter-test"):
        log.info("connecting with AKIAIOSFODNN7EXAMPLE")
    assert "AKIAIOSFODNN7EXAMPLE" not in caplog.text  # nosec B101
