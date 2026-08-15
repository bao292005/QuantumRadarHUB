"""Story 2.2 offline tests — decode offsets, keccak topic0, Aave era selection (FR8/FR9).

No network calls here; live extraction is exercised in Story 2.3.
"""
from tools import extract_fixtures as ex


def _enc(*words):
    """Encode signed/unsigned ints into a 0x data hex of 32-byte words."""
    return "0x" + "".join(format(w & (2 ** 256 - 1), "064x") for w in words)


def test_compound_topics_are_32byte_hex():
    for t in (ex.CMP_MINT, ex.CMP_BORROW, ex.CMP_REDEEM, ex.CMP_LIQUIDATE):
        assert t.startswith("0x") and len(t) == 66
    # topics must be distinct (each signature is unique)
    assert len({ex.CMP_MINT, ex.CMP_BORROW, ex.CMP_REDEEM, ex.CMP_LIQUIDATE}) == 4


def test_compound_borrow_topic_matches_known_keccak():
    # keccak256("Borrow(address,uint256,uint256,uint256)") — Compound cToken Borrow
    assert ex.CMP_BORROW == "0x13ed6866d4e1ee6da46f845c46d7e54120883d75c5ea9a2dacc1c4ca8984ab80"


def test_decode_uniswap_swap_signed():
    a0, a1 = ex.decode_amounts("uniswap_v3", "swap", _enc(-1000, 500))
    assert a0 == -1000 and a1 == 500


def test_decode_aave_borrow_word1():
    a0, a1 = ex.decode_amounts("aave_v2", "borrow", _enc(0xdead, 12345))
    assert a0 == 12345 and a1 == 0


def test_decode_aave_liquidation_word1_word0():
    a0, a1 = ex.decode_amounts("aave_v3", "liquidation", _enc(111, 222))
    assert a0 == 222 and a1 == 111


def test_decode_aave_withdraw_word0():
    a0, a1 = ex.decode_amounts("aave_v3", "withdraw", _enc(9999))
    assert a0 == 9999 and a1 == 0


def test_decode_compound_liquidation_repay_seize():
    a0, a1 = ex.decode_amounts("compound_v2", "liquidation", _enc(0, 0, 777, 0, 999))
    assert a0 == 777 and a1 == 999


def test_decode_short_data_safe():
    assert ex.decode_amounts("compound_v2", "liquidation", "0x") == (0, 0)


def test_era_selection_v2():
    subs = ex.subscriptions_for(14_724_000)  # before Jan 2023
    protos = {p for _, p, *_ in subs}
    assert "aave_v2" in protos
    assert "aave_v3" not in protos and "spark" not in protos


def test_era_selection_v3():
    subs = ex.subscriptions_for(16_820_000)  # after Jan 2023
    protos = {p for _, p, *_ in subs}
    assert "aave_v3" in protos and "spark" in protos
    assert "aave_v2" not in protos


def test_universe_has_13_base_contracts():
    # 9 Uniswap pools + 4 Compound cTokens (Aave/Spark added per era)
    assert len(ex.UNI_POOLS) == 9
    assert len(ex.COMPOUND) == 4
    assert len(ex.FIXTURES) == 12
