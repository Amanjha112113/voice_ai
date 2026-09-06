"""Metrics Aggregator and Percentile Calculator for EchoDrive.

Calculates and reports P50, P95, and P99 percentiles for latency benchmarks.
"""

from typing import List, Dict, Any, Optional
import math
import logging

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

from .telemetry import TurnTelemetry

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and aggregates latency metrics across multiple turns."""

    def __init__(self) -> None:
        self._turns: List[TurnTelemetry] = []

    def record_turn(self, telemetry: TurnTelemetry) -> None:
        self._turns.append(telemetry)

    def clear(self) -> None:
        self._turns.clear()

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    def compute_percentiles(self, values: List[float]) -> Dict[str, float]:
        if not values:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0}

        if np is not None:
            arr = np.array(values)
            return {
                "p50": float(np.percentile(arr, 50)),
                "p95": float(np.percentile(arr, 95)),
                "p99": float(np.percentile(arr, 99)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "avg": float(np.mean(arr)),
            }

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        def _calc_p(p: float) -> float:
            k = (n - 1) * (p / 100.0)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return float(sorted_vals[int(k)])
            return float(sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f))

        return {
            "p50": _calc_p(50),
            "p95": _calc_p(95),
            "p99": _calc_p(99),
            "min": float(min(sorted_vals)),
            "max": float(max(sorted_vals)),
            "avg": float(sum(sorted_vals) / n),
        }

    def summary(self) -> Dict[str, Any]:
        """Compute full statistical summary across all recorded turns."""
        ttfa_vals = [t.ttfa_ms for t in self._turns if t.ttfa_ms is not None]
        ttft_vals = [t.llm_ttft_ms for t in self._turns if t.llm_ttft_ms is not None]
        asr_vals = [t.asr_latency_ms for t in self._turns if t.asr_latency_ms is not None]
        tts_vals = [t.tts_first_audio_latency_ms for t in self._turns if t.tts_first_audio_latency_ms is not None]
        stop_vals = [t.interruption_stop_ms for t in self._turns if t.interruption_stop_ms is not None]

        return {
            "total_turns": len(self._turns),
            "ttfa_ms": self.compute_percentiles(ttfa_vals),
            "llm_ttft_ms": self.compute_percentiles(ttft_vals),
            "asr_latency_ms": self.compute_percentiles(asr_vals),
            "tts_latency_ms": self.compute_percentiles(tts_vals),
            "interruption_stop_ms": self.compute_percentiles(stop_vals),
        }

    def format_summary_table(self) -> str:
        """Format metrics as a clean markdown table."""
        s = self.summary()
        lines = [
            f"### Latency Benchmark Summary ({s['total_turns']} Turns)",
            "",
            "| Metric | P50 (ms) | P95 (ms) | P99 (ms) | Avg (ms) | Target | Status |",
            "|---|---|---|---|---|---|---|",
        ]

        def row(name: str, p: Dict[str, float], target_str: str, target_val: float) -> str:
            status = "✅ PASS" if p["p50"] <= target_val else "⚠️ EXCEEDS TARGET"
            return f"| {name} | {p['p50']:.1f} | {p['p95']:.1f} | {p['p99']:.1f} | {p['avg']:.1f} | {target_str} | {status} |"

        lines.append(row("TTFA (Time to First Audio)", s["ttfa_ms"], "≤ 700 ms", 700.0))
        lines.append(row("LLM TTFT (First Token)", s["llm_ttft_ms"], "≤ 350 ms", 350.0))
        lines.append(row("TTS First Audio", s["tts_latency_ms"], "≤ 150 ms", 150.0))
        lines.append(row("Interruption Stop Latency", s["interruption_stop_ms"], "≤ 200 ms", 200.0))

        return "\n".join(lines)
