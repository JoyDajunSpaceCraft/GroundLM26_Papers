"""Secure OpenReview authentication using the macOS Keychain."""

from __future__ import annotations

from dataclasses import dataclass
import re
import subprocess

import openreview


API_V2_URL = "https://api2.openreview.net"
DEFAULT_KEYCHAIN_SERVICE = "openreview.net"
_ACCOUNT_PATTERN = re.compile(r'"acct"<blob>="([^"]+)"')


class CredentialError(RuntimeError):
    """Raised when the OpenReview credential cannot be loaded safely."""


@dataclass(frozen=True, slots=True)
class KeychainCredential:
    username: str
    password: str


def _run_security(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/usr/bin/security", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def load_keychain_credential(
    service: str = DEFAULT_KEYCHAIN_SERVICE,
) -> KeychainCredential:
    metadata = _run_security(["find-generic-password", "-s", service])
    if metadata.returncode != 0:
        raise CredentialError(
            f"No readable macOS Keychain credential was found for service {service!r}."
        )

    account_match = _ACCOUNT_PATTERN.search(metadata.stdout)
    if not account_match:
        raise CredentialError(
            f"The macOS Keychain item for service {service!r} has no account name."
        )
    username = account_match.group(1)

    secret = _run_security(
        ["find-generic-password", "-s", service, "-a", username, "-w"]
    )
    password = secret.stdout.rstrip("\r\n")
    if secret.returncode != 0 or not password:
        raise CredentialError(
            f"The password for macOS Keychain service {service!r} could not be read."
        )

    return KeychainCredential(username=username, password=password)


def create_client(
    credential: KeychainCredential,
) -> openreview.api.OpenReviewClient:
    return openreview.api.OpenReviewClient(
        baseurl=API_V2_URL,
        username=credential.username,
        password=credential.password,
        tokenExpiresIn=86400,
    )
