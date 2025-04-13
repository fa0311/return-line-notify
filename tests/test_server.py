import pytest
from lotify.client import Client


@pytest.fixture(scope="session")
def client() -> Client:
    return Client(
        api_origin="http://127.0.0.1:8000",
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


if __name__ == "__main__":
    pass
