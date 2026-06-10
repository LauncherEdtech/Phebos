import importlib

import pytest


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """Módulo config apontando para um DATA_DIR temporário."""
    monkeypatch.setenv("PHEBOS_DATA_DIR", str(tmp_path))
    import phebos.config
    importlib.reload(phebos.config)
    return phebos.config


# ── intervalo dinâmico ──────────────────────────────────────────────
def test_intervalo_padrao_quando_nao_ha_runtime(cfg):
    assert cfg.get_runtime_interval(15) == 15


def test_salvar_e_ler_intervalo(cfg):
    assert cfg.set_runtime_interval(30) == 30
    assert cfg.get_runtime_interval(15) == 30


def test_intervalo_minimo_de_1(cfg):
    assert cfg.set_runtime_interval(0) == 1
    assert cfg.set_runtime_interval(-5) == 1


def test_runtime_corrompido_cai_no_default(cfg):
    cfg.RUNTIME_FILE.write_text("{lixo invalido")
    assert cfg.get_runtime_interval(15) == 15


def test_runtime_com_valor_invalido_cai_no_default(cfg):
    import json
    cfg.RUNTIME_FILE.write_text(json.dumps({"interval_minutes": 0}))
    assert cfg.get_runtime_interval(20) == 20


def test_escrita_de_intervalo_eh_atomica(cfg):
    cfg.set_runtime_interval(45)
    # não deve sobrar o arquivo temporário
    assert not cfg.RUNTIME_FILE.with_suffix(".tmp").exists()
    assert cfg.get_runtime_interval(15) == 45


# ── rodar agora ─────────────────────────────────────────────────────
def test_run_now_request_e_consume(cfg):
    assert cfg.consume_run_now() is False  # nada pendente
    cfg.request_run_now()
    assert cfg.consume_run_now() is True   # consumiu
    assert cfg.consume_run_now() is False  # já foi consumido (one-shot)


def test_run_now_idempotente_no_request(cfg):
    cfg.request_run_now()
    cfg.request_run_now()  # segundo pedido não acumula
    assert cfg.consume_run_now() is True
    assert cfg.consume_run_now() is False


# ── resolução do config.yaml (bug do Docker: pacote em site-packages) ──
def test_find_config_prioriza_env(cfg, tmp_path, monkeypatch):
    custom = tmp_path / "meu_config.yaml"
    custom.write_text("mode: demo")
    monkeypatch.setenv("PHEBOS_CONFIG", str(custom))
    import importlib
    importlib.reload(cfg)
    assert cfg.find_config() == custom


def test_find_config_acha_no_cwd(cfg, tmp_path, monkeypatch):
    monkeypatch.delenv("PHEBOS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("mode: demo")
    import importlib
    importlib.reload(cfg)
    assert cfg.find_config() == tmp_path / "config.yaml"
