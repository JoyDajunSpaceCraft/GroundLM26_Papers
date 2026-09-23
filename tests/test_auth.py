from subprocess import CompletedProcess

import pytest

from groundlm_collector.auth import (
    CredentialError,
    create_client,
    load_keychain_credential,
)


def test_load_keychain_credential_extracts_account_without_printing_password(
    monkeypatch, capsys
):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[-1] == "-w":
            return CompletedProcess(args, 0, "secret\n", "")
        return CompletedProcess(
            args,
            0,
            'keychain: "/Users/test/Library/Keychains/login.keychain-db"\n'
            'class: "genp"\n'
            'attributes:\n'
            '    "acct"<blob>="chair@example.com"\n',
            "",
        )

    monkeypatch.setattr("subprocess.run", fake_run)
    credential = load_keychain_credential()

    assert credential.username == "chair@example.com"
    assert credential.password == "secret"
    assert "secret" not in capsys.readouterr().out
    assert all("secret" not in part for call in calls for part in call)


def test_load_keychain_credential_fails_when_service_is_missing(monkeypatch):
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: CompletedProcess(args, 44, "", "not found"),
    )

    with pytest.raises(CredentialError, match="openreview.net"):
        load_keychain_credential()


def test_create_client_uses_api_v2_and_one_day_token(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("openreview.api.OpenReviewClient", FakeClient)
    credential = type(
        "Credential", (), {"username": "chair@example.com", "password": "secret"}
    )()

    client = create_client(credential)

    assert isinstance(client, FakeClient)
    assert captured == {
        "baseurl": "https://api2.openreview.net",
        "username": "chair@example.com",
        "password": "secret",
        "tokenExpiresIn": 86400,
    }
