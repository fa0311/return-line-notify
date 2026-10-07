import pytest
from lotify.client import Client

from tests.conftest import integration_enabled

# 実際に起動したサーバーに対して通知を送る。RLN_INTEGRATION=1 のときだけ実行
pytestmark = pytest.mark.skipif(
    not integration_enabled(), reason="set RLN_INTEGRATION=1 to run"
)


@pytest.fixture(scope="session")
def client() -> Client:
    return Client(
        api_origin="http://127.0.0.1:3333",
    )


def test_send_message(client: Client):
    res = client.send_message("336355274:10", "test")
    assert res["status"] == "ok"


def test_send_sticker(client: Client):
    res = client.send_message_with_sticker(
        "336355274:10",
        "test",
        sticker_id=1,
        sticker_package_id=1,
    )
    assert res["status"] == "ok"


def test_send_image(client: Client):
    res = client.send_message_with_image_file(
        "336355274:10",
        "test",
        file=open("tests/assets/sample.png", "rb"),
    )
    assert res["status"] == "ok"
