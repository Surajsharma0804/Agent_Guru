"""Paths holding keys and credentials are refused, and ordinary files are not.

Nothing tested sensitive_reason() directly. A side-by-side run on 28 paths
found it missed the PostgreSQL password file, and refused a public key
outside ~/.ssh only because its name starts like a private key's.
"""

from __future__ import annotations

import pytest

from Agent_Guru.security.file_policy import SensitivePathError, check_path, sensitive_reason


@pytest.mark.parametrize("path", [
    "~/.ssh/id_rsa", "~/.ssh/id_ed25519", "~/.ssh/config", "~/.ssh/authorized_keys", "~/.ssh/id_rsa.pub",
    "project/.env", "project/.env.local", "~/.aws/credentials", "~/.netrc", "certs/server.pem",
    "certs/private.key", "~/.kube/config", "~/.docker/config.json", "~/.git-credentials",
    "secrets/credentials.json", "keystore.p12", "/etc/shadow", "C:/Windows/System32/config/SAM",
    "C:/Users/alice/AppData/Local/Google/Chrome/User Data/Default/Login Data",
    # Added after the side-by-side run.
    "~/.pgpass", "C:/Users/alice/AppData/Roaming/postgresql/pgpass.conf", "~/.my.cnf", "~/.s3cfg",
    "~/.vault-token", "~/.terraformrc", "~/.config/gh/hosts.yml",
    "C:/Users/alice/AppData/Roaming/GitHub CLI/hosts.yml",
    "~/.config/gcloud/application_default_credentials.json",
])
def test_key_and_credential_paths_are_sensitive(path):
    assert sensitive_reason(path)  # nosec B101
    with pytest.raises(SensitivePathError):
        check_path(path, "read")


@pytest.mark.parametrize("path", [
    "keys/id_rsa.pub",  # a public key outside .ssh holds nothing secret
    "project/.env.example", "notes/todo.txt", "Documents/report.pdf", "src/main.py",
    "photos/holiday.jpg", "project/environment.yml", "README.md",
    "ansible/hosts.yml",  # an inventory file, not the GitHub CLI's token
])
def test_ordinary_paths_are_not(path):
    assert sensitive_reason(path) == ""  # nosec B101
    check_path(path, "read")


def test_the_whole_ssh_folder_stays_refused_even_for_public_files():
    # Writing a public key into authorized_keys would let anyone in, so
    # inside .ssh nothing is handed to the assistant.
    assert sensitive_reason("~/.ssh/id_rsa.pub") == "SSH keys"  # nosec B101
