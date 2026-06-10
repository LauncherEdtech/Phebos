"""Avaliação do período demo: métricas e veredito de aptidão ao modo real."""

from dataclasses import dataclass
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

    @property
    def approved(self) -> bool:
        return bool(self.criteria) and all(ok for _, ok in self.criteria)


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

    criteria = [
        (f"tempo em demo ≥ {config.min_days} dias (atual: {days:.1f})", days >= config.min_days),
        (f"trades executados ≥ {config.min_trades} (atual: {trades})", trades >= config.min_trades),
        (f"retorno total ≥ {config.min_return_pct}% (atual: {return_pct:+.2f}%)",
         return_pct >= config.min_return_pct),
        (f"drawdown máximo ≤ {config.max_drawdown_pct}% (atual: {max_dd:.2f}%)",
         max_dd <= config.max_drawdown_pct),
    ]
    return DemoReport(
        days_running=days,
        trade_count=trades,
        return_pct=return_pct,
        max_drawdown_pct=max_dd,
        criteria=criteria,
    )


def print_report(report: DemoReport | None) -> None:
    if report is None:
        print("Ainda não há dados suficientes no journal — rode o agente em modo demo primeiro.")
        return
    print("═══ Relatório do período demo ═══")
    print(f"  Tempo rodando : {report.days_running:.1f} dias")
    print(f"  Trades        : {report.trade_count}")
    print(f"  Retorno total : {report.return_pct:+.2f}%")
    print(f"  Drawdown máx. : {report.max_drawdown_pct:.2f}%")
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
