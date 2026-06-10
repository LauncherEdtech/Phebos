"""Avaliação do período demo: métricas profissionais e veredito de aptidão ao modo real."""

from dataclasses import dataclass, field
from datetime import datetime

from .config import DemoConfig
from .journal import Journal


@dataclass
class DemoReport:
    days_running: float
    trade_count: int
    return_pct: float
    max_drawdown_pct: float
    criteria: list[tuple[str, bool]]
    # métricas profissionais (saídas realizadas)
    closed_trades: int = 0
    realized_pnl_usd: float = 0.0
    win_rate_pct: float | None = None
    profit_factor: float | None = None
    avg_win_usd: float = 0.0
    avg_loss_usd: float = 0.0
    benchmark_return_pct: float | None = None
    criteria_extra: list = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return bool(self.criteria) and all(ok for _, ok in self.criteria)

    @property
    def alpha_pct(self) -> float | None:
        """Quanto o agente fez ACIMA do buy-and-hold (a métrica que importa)."""
        if self.benchmark_return_pct is None:
            return None
        return self.return_pct - self.benchmark_return_pct


def evaluate_demo(journal: Journal, config: DemoConfig) -> DemoReport | None:
    series = journal.equity_series("demo")
    if len(series) < 2:
        return None

    first_ts = datetime.fromisoformat(series[0][0])
    last_ts = datetime.fromisoformat(series[-1][0])
    days = (last_ts - first_ts).total_seconds() / 86400

    values = [v for _, v in series if v]
    start, end = values[0], values[-1]
    return_pct = (end - start) / start * 100 if start else 0.0

    peak = values[0]
    max_dd = 0.0
    for v in values:
        peak = max(peak, v)
        if peak:
            max_dd = max(max_dd, (peak - v) / peak * 100)

    trades = len(journal.executed_trades("demo"))
    stats = journal.realized_stats("demo")
    benchmark = journal.benchmark_return_pct("demo")

    criteria = [
        (f"tempo em demo ≥ {config.min_days} dias (atual: {days:.1f})", days >= config.min_days),
        (f"trades executados ≥ {config.min_trades} (atual: {trades})", trades >= config.min_trades),
        (f"retorno total ≥ {config.min_return_pct}% (atual: {return_pct:+.2f}%)",
         return_pct >= config.min_return_pct),
        (f"drawdown máximo ≤ {config.max_drawdown_pct}% (atual: {max_dd:.2f}%)",
         max_dd <= config.max_drawdown_pct),
    ]
    if config.must_beat_benchmark and benchmark is not None:
        criteria.append((
            f"retorno ≥ buy-and-hold dos símbolos ({benchmark:+.2f}%) — "
            f"senão era melhor só comprar e segurar",
            return_pct >= benchmark,
        ))

    return DemoReport(
        days_running=days,
        trade_count=trades,
        return_pct=return_pct,
        max_drawdown_pct=max_dd,
        criteria=criteria,
        closed_trades=stats["closed_trades"],
        realized_pnl_usd=stats["realized_pnl_usd"],
        win_rate_pct=stats["win_rate_pct"],
        profit_factor=stats["profit_factor"],
        avg_win_usd=stats["avg_win_usd"],
        avg_loss_usd=stats["avg_loss_usd"],
        benchmark_return_pct=benchmark,
    )


def print_report(report: DemoReport | None) -> None:
    if report is None:
        print("Ainda não há dados suficientes no journal — rode o agente em modo demo primeiro.")
        return
    pf = ("∞" if report.profit_factor == float("inf")
          else f"{report.profit_factor:.2f}" if report.profit_factor is not None else "—")
    wr = f"{report.win_rate_pct:.1f}%" if report.win_rate_pct is not None else "—"
    bench = (f"{report.benchmark_return_pct:+.2f}%"
             if report.benchmark_return_pct is not None else "—")
    alpha = f"{report.alpha_pct:+.2f}%" if report.alpha_pct is not None else "—"

    print("═══ Relatório do período demo ═══")
    print(f"  Tempo rodando      : {report.days_running:.1f} dias")
    print(f"  Trades (ordens)    : {report.trade_count}")
    print(f"  Retorno total      : {report.return_pct:+.2f}%")
    print(f"  Benchmark (B&H)    : {bench}   →  alfa: {alpha}")
    print(f"  Drawdown máx.      : {report.max_drawdown_pct:.2f}%")
    print("  ─── Saídas realizadas ───")
    print(f"  Posições fechadas  : {report.closed_trades}")
    print(f"  P&L realizado      : ${report.realized_pnl_usd:+.2f}")
    print(f"  Taxa de acerto     : {wr}")
    print(f"  Fator de lucro     : {pf}  (ganho bruto / perda bruta)")
    print(f"  Ganho médio        : ${report.avg_win_usd:+.2f} | Perda média: ${report.avg_loss_usd:+.2f}")
    print("\n  Critérios para o modo real:")
    for label, ok in report.criteria:
        print(f"    [{'✔' if ok else '✘'}] {label}")
    print()
    if report.approved:
        print("✅ Critérios atingidos. Para ir ao modo real: mode: live no config.yaml,")
        print("   chaves LIVE no .env e PHEBOS_CONFIRM_LIVE=EU_ACEITO_O_RISCO no ambiente.")
    else:
        print("⏳ Critérios ainda não atingidos. Você pode promover mesmo assim (a decisão")
        print("   é sua), seguindo os mesmos passos acima — mas não é recomendado.")
