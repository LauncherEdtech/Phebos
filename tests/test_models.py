from pixzap.models import format_brl, parse_brl


def test_parse_brl_formats():
    assert parse_brl("150") == 15000
    assert parse_brl("150,50") == 15050
    assert parse_brl("R$ 1.500,50") == 150050
    assert parse_brl("r$89,90") == 8990


def test_parse_brl_invalid():
    assert parse_brl("abc") is None
    assert parse_brl("0") is None
    assert parse_brl("-10") is None
    assert parse_brl("999999999999") is None  # acima do limite de sanidade


def test_format_brl():
    assert format_brl(15000) == "R$ 150,00"
    assert format_brl(150050) == "R$ 1.500,50"
    assert format_brl(5) == "R$ 0,05"
