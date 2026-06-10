import importlib

import pytest


@pytest.fixture
def keys_mod(tmp_path, monkeypatch):
    """Módulo keys apontando para um secrets.env temporário e ambiente limpo."""
    monkeypatch.setenv("PHEBOS_DATA_DIR", str(tmp_path))
    for field in ("GEMINI_API_KEY", "BINANCE_TESTNET_API_KEY", "BINANCE_TESTNET_API_SECRET",
                  "ALPACA_PAPER_API_KEY", "ALPACA_PAPER_API_SECRET",
                  "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(field, raising=False)
    import phebos.config, phebos.keys
    importlib.reload(phebos.config)
    importlib.reload(phebos.keys)
    return phebos.keys


def test_save_merge_e_leitura(keys_mod):
    saved = keys_mod.save_secrets({"GEMINI_API_KEY": "abc123XYZ789", "VAZIO": ""})
    assert saved == ["GEMINI_API_KEY"]
    # segunda gravação não apaga a primeira
    keys_mod.save_secrets({"TELEGRAM_CHAT_ID": "42"})
    secrets = keys_mod.read_secrets()
    assert secrets["GEMINI_API_KEY"] == "abc123XYZ789"
    assert secrets["TELEGRAM_CHAT_ID"] == "42"


def test_arquivo_tem_permissao_restrita(keys_mod):
    keys_mod.save_secrets({"GEMINI_API_KEY": "abc"})
    from phebos.config import SECRETS_FILE
    assert oct(SECRETS_FILE.stat().st_mode)[-3:] == "600"


def test_status_mascarado_nunca_expoe_chave(keys_mod):
    keys_mod.save_secrets({"GEMINI_API_KEY": "AIzaSuperSecreta1234"})
    status = keys_mod.masked_status()
    assert status["GEMINI_API_KEY"]["set"] is True
    preview = status["GEMINI_API_KEY"]["preview"]
    assert "SuperSecreta" not in preview
    assert preview == "AIza…1234"
    assert status["TELEGRAM_BOT_TOKEN"] == {"set": False, "preview": ""}


def test_secrets_sobrescrevem_ambiente(keys_mod, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "do-ambiente")
    assert keys_mod.effective_value("GEMINI_API_KEY") == "do-ambiente"
    keys_mod.save_secrets({"GEMINI_API_KEY": "do-dashboard"})
    assert keys_mod.effective_value("GEMINI_API_KEY") == "do-dashboard"


def test_testes_pulam_servicos_sem_chave(keys_mod):
    results = keys_mod.run_tests()
    assert all(r["ok"] is None for r in results.values())


def test_telegram_token_invalido(keys_mod, monkeypatch):
    keys_mod.save_secrets({"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "1"})

    class FakeResp:
        def json(self):
            return {"ok": False, "description": "Unauthorized"}
    monkeypatch.setattr("phebos.keys.requests.get", lambda *a, **k: FakeResp())
    result = keys_mod.test_telegram()
    assert result["ok"] is False and "Unauthorized" in result["detail"]


def test_telegram_envia_mensagem_de_teste(keys_mod, monkeypatch):
    keys_mod.save_secrets({"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "42"})
    sent = {}

    class FakeResp:
        def __init__(self, payload): self._p = payload
        def json(self): return self._p

    monkeypatch.setattr("phebos.keys.requests.get",
                        lambda *a, **k: FakeResp({"ok": True, "result": {"username": "phebos_bot"}}))
    def fake_post(url, json=None, timeout=None):
        sent.update(json)
        return FakeResp({"ok": True})
    monkeypatch.setattr("phebos.keys.requests.post", fake_post)

    result = keys_mod.test_telegram()
    assert result["ok"] is True and "phebos_bot" in result["detail"]
    assert sent["chat_id"] == "42"


def test_binance_usa_broker_testnet(keys_mod, monkeypatch):
    keys_mod.save_secrets({"BINANCE_TESTNET_API_KEY": "k", "BINANCE_TESTNET_API_SECRET": "s"})
    monkeypatch.setattr(
        "phebos.brokers.binance.BinanceBroker._signed",
        lambda self, m, p: {"balances": [{"free": "1", "locked": "0"}, {"free": "0", "locked": "0"}]})
    result = keys_mod.test_binance()
    assert result["ok"] is True and "1 ativos" in result["detail"]


def test_binance_erro_retorna_detalhe(keys_mod, monkeypatch):
    keys_mod.save_secrets({"BINANCE_TESTNET_API_KEY": "k", "BINANCE_TESTNET_API_SECRET": "s"})
    def boom(self, m, p):
        raise RuntimeError("401 Invalid API-key")
    monkeypatch.setattr("phebos.brokers.binance.BinanceBroker._signed", boom)
    result = keys_mod.test_binance()
    assert result["ok"] is False and "Invalid API-key" in result["detail"]
