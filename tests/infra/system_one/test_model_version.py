"""How the HTTP judge resolves its model's version from the server's models."""

import asyncio

from klint.infra.system_one import HttpSystemOneJudge
from tests.support.stub_system_one_server import StubSystemOneServer


def _resolve(server: StubSystemOneServer, model_name: str = "jev-latest") -> str | None:
    judge = HttpSystemOneJudge(
        model_name=model_name, base_url=server.base_url, api_key="secret"
    )
    return asyncio.run(judge.resolve_model_version())


def test_version_is_the_models_card_and_changes_with_its_release(
    system_one_server: StubSystemOneServer,
) -> None:
    version = _resolve(system_one_server)

    (received,) = system_one_server.received
    assert received.method == "GET"
    assert received.path == "/v1/models"
    assert received.headers["Authorization"] == "Bearer secret"
    assert version == (
        "name=jev-latest release_date=2026-01-01 description=The stub's jev-latest"
    )
    assert _resolve(system_one_server, "kev-latest") != version


def test_name_the_server_does_not_list_is_a_version_in_itself(
    system_one_server: StubSystemOneServer,
) -> None:
    assert _resolve(system_one_server, "jev-1.14.0") == "name=jev-1.14.0"


def test_run_a_kev_server_names_on_its_cards_resolves_to_that_card(
    system_one_server: StubSystemOneServer,
) -> None:
    system_one_server.run_name = "jaredpalmer/kev-4b"

    assert _resolve(system_one_server, "jaredpalmer/kev-4b") == _resolve(
        system_one_server, "kev-latest"
    )


def test_server_that_cannot_list_its_models_gives_no_version(
    system_one_server: StubSystemOneServer,
) -> None:
    system_one_server.models_response_status = 500

    assert _resolve(system_one_server) is None
