import pytest
import re
from cutecoin.models.coin import Coin


issuer = "2E69197FAB029D8669EF85E82457A1587CA0ED9C"
number = "0"
base = "1"
power = "1"
origin = "A-2"


@pytest.fixture
def coin_id_regex():
    return re.compile("^([A-Z\d]{40})-(\d+)-(\d)-(\d+)-((A|F|D)-\d+)$")


def test_coin_init(coin_id_regex):
    coin = Coin(issuer, number, base, power, origin)
    assert coin_id_regex.match(coin.get_id()) is not None


def test_coin_from_id(coin_id_regex):
    coin_id = issuer + "-" + number + "-" + base + "-" + power + "-" + origin
    coin = Coin.from_id(coin_id)
    assert coin is not None
    assert coin_id_regex.match(coin.get_id()) is not None
