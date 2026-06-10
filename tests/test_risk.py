from conftest import make_position, make_snapshot

from phebos.config import RiskConfig
from phebos.risk import RiskEngine
from phebos.schemas import OrderDecision, Position


def order(symbol="BTCUSDT", side="buy", notional=40.0, confidence="high", event_key=None):
    return OrderDecision(symbol=symbol, side=side, notional_usd=notional,
                         confidence=confidence, rationale="teste", event_key=event_key)


def engine(**kw):
    return RiskEngine(RiskConfig(**kw))


def review(eng, orders, snap=None, allowed=None, daily=0.0, acted=None, atr=None,
           regime="alta"):
    return eng.review(orders, snap or make_snapshot(), allowed or ["BTCUSDT", "ETHUSDT"],
                      daily, acted, atr, regime)


# ── vetos básicos ───────────────────────────────────────────────────
def test_aprova_ordem_valida():
    v = review(engine(), [order()])[0]
    assert v.approved


def test_veta_simbolo_fora_da_lista():
    v = review(engine(), [order(symbol="DOGEUSDT")])[0]
    assert not v.approved and "fora da lista" in v.reason


def test_veta_abaixo_do_minimo():
    v = review(engine(), [order(notional=5)])[0]
    assert not v.approved and "mínimo" in v.reason


def test_veta_perda_diaria_excedida():
    v = review(engine(), [order()], daily=-5.0)[0]
    assert not v.approved and "perda diária" in v.reason


def test_veta_venda_sem_posicao():
    v = review(engine(), [order(side="sell")])[0]
    assert not v.approved and "sem posição" in v.reason


def test_aprova_venda_com_posicao():
    pos = Position(symbol="BTCUSDT", qty=1, avg_price=90, market_value=100, unrealized_pnl=10)
    snap = make_snapshot(positions=[pos])
    v = review(engine(), [order(side="sell")], snap=snap)[0]
    assert v.approved


def test_veta_caixa_insuficiente():
    snap = make_snapshot(cash=10.0)
    v = review(engine(), [order(notional=40)], snap=snap)[0]
    assert not v.approved and "caixa" in v.reason.lower()


def test_veta_max_posicoes():
    positions = [Position(symbol=f"S{i}", qty=1, avg_price=1, market_value=1, unrealized_pnl=0)
                 for i in range(6)]
    snap = make_snapshot(positions=positions)
    v = review(engine(max_open_positions=6), [order()], snap=snap)[0]
    assert not v.approved and "posições abertas" in v.reason


def test_compra_em_simbolo_ja_aberto_nao_conta_posicao_nova():
    positions = [Position(symbol="BTCUSDT", qty=1, avg_price=1, market_value=1, unrealized_pnl=0)]
    snap = make_snapshot(positions=positions)
    v = review(engine(max_open_positions=1), [order()], snap=snap)[0]
    assert v.approved


# ── dedupe de eventos ───────────────────────────────────────────────
def test_veta_evento_ja_operado():
    acted = {("BTCUSDT", "buy", "eua-reserva-btc")}
    v = review(engine(), [order(event_key="eua-reserva-btc")], acted=acted)[0]
    assert not v.approved and "já foi operado" in v.reason


def test_mesmo_evento_outro_lado_passa():
    acted = {("BTCUSDT", "buy", "eua-reserva-btc")}
    pos = Position(symbol="BTCUSDT", qty=1, avg_price=90, market_value=100, unrealized_pnl=0)
    snap = make_snapshot(positions=[pos])
    v = review(engine(), [order(side="sell", event_key="eua-reserva-btc")],
               snap=snap, acted=acted)[0]
    assert v.approved


def test_ordem_sem_event_key_nao_sofre_dedupe():
    acted = {("BTCUSDT", "buy", "evento-x")}
    v = review(engine(), [order(event_key=None)], acted=acted)[0]
    assert v.approved


# ── dimensionamento dinâmico ────────────────────────────────────────
def test_cap_conviccao_alta_mercado_alta():
    eng = engine()
    cap = eng.position_cap_usd(1000, "high", atr_pct=4.0, regime="alta")
    assert abs(cap - 50.0) < 0.01  # 5% × 1.0 × 1.0 × 1.0


def test_cap_conviccao_baixa_reduz():
    eng = engine()
    assert abs(eng.position_cap_usd(1000, "low", 4.0, "alta") - 20.0) < 0.01


def test_cap_volatilidade_alta_reduz():
    eng = engine()
    cap = eng.position_cap_usd(1000, "high", atr_pct=8.0, regime="alta")
    assert abs(cap - 25.0) < 0.01  # vol_scalar = 4/8 = 0.5


def test_cap_volatilidade_baixa_aumenta_limitado():
    eng = engine()
    cap = eng.position_cap_usd(1000, "high", atr_pct=1.0, regime="alta")
    assert abs(cap - 62.5) < 0.01  # clamp em 1.25


def test_cap_regime_baixa_corta_pela_metade():
    eng = engine()
    assert abs(eng.position_cap_usd(1000, "high", 4.0, "baixa") - 25.0) < 0.01


def test_ordem_grande_eh_redimensionada_nao_vetada():
    v = review(engine(), [order(notional=500)], atr={"BTCUSDT": 4.0})[0]
    assert v.approved
    assert "redimensionada" in v.reason
    assert abs(v.order.notional_usd - 50.0) < 0.01


def test_redimensionamento_abaixo_do_minimo_veta():
    # convicção low + vol alta + regime baixa → cap = 50×0.4×0.5×0.5 = $5 < $10
    v = review(engine(), [order(notional=500, confidence="low")],
               atr={"BTCUSDT": 8.0}, regime="baixa")[0]
    assert not v.approved and "abaixo da ordem mínima" in v.reason


def test_venda_nao_sofre_redimensionamento():
    pos = Position(symbol="BTCUSDT", qty=10, avg_price=90, market_value=1000, unrealized_pnl=0)
    snap = make_snapshot(positions=[pos])
    v = review(engine(), [order(side="sell", notional=500)], snap=snap)[0]
    assert v.approved and v.order.notional_usd == 500


# ── disciplina de saída ─────────────────────────────────────────────
def test_stop_loss_dispara():
    eng = engine(stop_loss_pct=8)
    sigs = eng.check_exits([make_position(avg=100, last=91)], {"BTCUSDT": 91.0})
    assert len(sigs) == 1 and sigs[0].reason == "stop_loss"


def test_stop_loss_nao_dispara_antes_do_limite():
    eng = engine(stop_loss_pct=8)
    assert eng.check_exits([make_position(avg=100)], {"BTCUSDT": 93.0}) == []


def test_take_profit_dispara():
    eng = engine(take_profit_pct=15)
    sigs = eng.check_exits([make_position(avg=100)], {"BTCUSDT": 116.0})
    assert sigs and sigs[0].reason == "take_profit"


def test_trailing_stop_dispara():
    eng = engine(trailing_stop_pct=5, stop_loss_pct=50, take_profit_pct=100)
    pos = make_position(avg=100, peak=120)
    sigs = eng.check_exits([pos], {"BTCUSDT": 113.0})
    assert sigs and sigs[0].reason == "trailing_stop"


def test_trailing_desativado_por_padrao():
    eng = engine(stop_loss_pct=50, take_profit_pct=100)
    assert eng.check_exits([make_position(avg=100, peak=120)], {"BTCUSDT": 113.0}) == []


def test_exit_sem_preco_eh_ignorado():
    eng = engine()
    assert eng.check_exits([make_position()], {}) == []


def test_exit_notional_eh_posicao_inteira():
    eng = engine(stop_loss_pct=8)
    sigs = eng.check_exits([make_position(qty=2, avg=100, last=90)], {"BTCUSDT": 90.0})
    assert abs(sigs[0].notional_usd - 180.0) < 0.01


# ── circuit breaker anti-tilt ───────────────────────────────────────
def test_anti_tilt_reduz_sizing_apos_3_perdas():
    eng = engine()
    cap_normal = eng.position_cap_usd(1000, "high", 4.0, "alta", loss_streak=0)
    cap_tilt = eng.position_cap_usd(1000, "high", 4.0, "alta", loss_streak=3)
    assert abs(cap_tilt - cap_normal * 0.5) < 0.01


def test_anti_tilt_nao_ativa_abaixo_do_limite():
    eng = engine()
    assert eng.position_cap_usd(1000, "high", 4.0, "alta", loss_streak=2) == \
           eng.position_cap_usd(1000, "high", 4.0, "alta", loss_streak=0)


def test_anti_tilt_no_review_redimensiona():
    v = review_with_streak(engine(), [order(notional=50)], streak=3)[0]
    assert v.approved and abs(v.order.notional_usd - 25.0) < 0.01


def review_with_streak(eng, orders, streak):
    return eng.review(orders, make_snapshot(), ["BTCUSDT"], 0.0, None,
                      {"BTCUSDT": 4.0}, "alta", streak)
