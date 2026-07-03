"""Parser e formatação de dinheiro: estilos pt e en, moedas por mercado."""

import pytest

from pixzap.models import format_money, parse_brl, set_currency


@pytest.fixture(autouse=True)
def reset_currency():
    yield
    set_currency("BRL")


def test_parse_pt_style():
    assert parse_brl("150") == 15000
    assert parse_brl("150,50") == 15050
    assert parse_brl("150,5") == 15050
    assert parse_brl("R$ 1.500,50") == 150050
    assert parse_brl("1.500") == 150000       # ponto de milhar


def test_parse_en_style():
    # bug corrigido: "150.00" era lido como R$ 15.000,00
    assert parse_brl("150.00") == 15000
    assert parse_brl("1,500.50") == 150050
    assert parse_brl("1,500") == 150000       # vírgula de milhar


def test_parse_invalid():
    assert parse_brl("abc") is None
    assert parse_brl("0") is None
    assert parse_brl("1.5000") is None        # separador sem sentido
    assert parse_brl("999999999999") is None  # acima do limite de sanidade


def test_format_currencies():
    assert format_money(150050) == "R$ 1.500,50"
    set_currency("NGN")
    assert format_money(150050) == "₦ 1,500.50"
    set_currency("IDR")
    assert format_money(15000000) == "Rp 150.000"  # sem casas decimais
    set_currency("MXN")
    assert format_money(15050) == "$ 150.50"


def test_unknown_currency_rejected():
    with pytest.raises(ValueError):
        set_currency("XYZ")
