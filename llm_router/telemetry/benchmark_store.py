import json
import math
import sqlite3
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque, Dict, Optional, Sequence

LOCAL_BACKENDS = {"ollama", "gguf", "hf_local", "gpt4all", "lmstudio"}


class BenchmarkStore:
    def __init__(
        self,
        history_size: int = 50,
        sqlite_path: Optional[str] = None,
    ):
        self.history_size = history_size
        self.sqlite_path = sqlite_path
        self._lock = threading.RLock()
        self._latencies: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=self.history_size)
        )
        self._ttft: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=self.history_size)
        )
        self._tokens_per_second: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=self.history_size)
        )
        self._queue_depth: Dict[str, Deque[int]] = defaultdict(
            lambda: deque(maxlen=self.history_size)
        )
        self._pending_requests: Dict[str, int] = defaultdict(int)
        self._started_at: Dict[str, float] = {}
        self._sample_sources: Dict[str, Deque[str]] = defaultdict(
            lambda: deque(maxlen=self.history_size)
        )
        self._canary_counts: Dict[str, int] = defaultdict(int)
        self._last_sample_at: Dict[str, float] = {}
        self._backend_profiles: Dict[str, Dict[str, Any]] = {}

        if self.sqlite_path:
            self._ensure_sqlite()

    def start_request(self, backend: str) -> float:
        token = time.perf_counter()
        with self._lock:
            self._pending_requests[backend] += 1
            self._started_at[f"{backend}:{token}"] = token
        return token

    def finish_request(
        self,
        backend: str,
        started_at: float,
        duration_ms: float,
        token_count: int,
        ttft_ms: Optional[float] = None,
    ) -> None:
        key = f"{backend}:{started_at}"
        with self._lock:
            self._started_at.pop(key, None)
            self._pending_requests[backend] = max(
                0, self._pending_requests[backend] - 1
            )
            queue_depth = self._pending_requests[backend]
        self.record_benchmark_sample(
            backend=backend,
            duration_ms=duration_ms,
            token_count=token_count,
            ttft_ms=ttft_ms,
            queue_depth=queue_depth,
            source="request",
        )

    def record_benchmark_sample(
        self,
        backend: str,
        duration_ms: float,
        token_count: int,
        ttft_ms: Optional[float] = None,
        queue_depth: Optional[int] = None,
        source: str = "canary",
        metadata: Optional[Dict[str, Any]] = None,
        recorded_at: Optional[float] = None,
    ) -> Dict[str, Any]:
        if recorded_at is None:
            recorded_at = time.time()
        if queue_depth is None:
            queue_depth = self.pending_requests(backend)

        tokens_per_second = (
            (token_count / duration_ms) * 1000.0
            if duration_ms > 0 and token_count > 0
            else None
        )
        row = {
            "backend": backend,
            "recorded_at": recorded_at,
            "source": source,
            "duration_ms": duration_ms,
            "token_count": token_count,
            "ttft_ms": ttft_ms,
            "tokens_per_second": tokens_per_second,
            "queue_depth": queue_depth,
            "metadata": metadata or {},
        }

        with self._lock:
            self._latencies[backend].append(duration_ms)
            if ttft_ms is not None:
                self._ttft[backend].append(ttft_ms)
            if tokens_per_second is not None:
                self._tokens_per_second[backend].append(tokens_per_second)
            self._queue_depth[backend].append(queue_depth)
            self._sample_sources[backend].append(source)
            self._last_sample_at[backend] = recorded_at
            if source == "canary":
                self._canary_counts[backend] += 1

        if self.sqlite_path:
            self._persist_row(row)
        return row

    def register_backend_profile(
        self,
        backend: str,
        *,
        downgrade_backends: Optional[Sequence[str]] = None,
        cloud_fallback: Optional[str] = None,
        target_model: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> None:
        self._backend_profiles[backend] = {
            "downgrade_backends": list(downgrade_backends or []),
            "cloud_fallback": cloud_fallback,
            "target_model": target_model,
            "tags": list(tags or []),
        }

    def summary(self, backend: Optional[str] = None) -> Dict[str, Any]:
        if backend is not None:
            return self._summary_for_backend(backend)
        names = (
            set(self._latencies)
            | set(self._pending_requests)
            | set(self._backend_profiles)
        )
        return {name: self._summary_for_backend(name) for name in sorted(names)}

    def pending_requests(self, backend: Optional[str] = None) -> Any:
        with self._lock:
            if backend is not None:
                return self._pending_requests.get(backend, 0)
            return {
                name: count for name, count in sorted(self._pending_requests.items())
            }

    def local_viability(
        self,
        backend: str,
        hardware_status: Dict[str, Any],
        privacy_priority: float = 0.0,
        quality_weight: float = 0.40,
        availability_weight: float = 0.20,
        privacy_weight: float = 0.25,
    ) -> float:
        summary = self._summary_for_backend(backend)
        benchmark_score = min((summary["tokens_per_second_ewma"] or 0.0) / 120.0, 1.0)
        model_ready = 1.0 if summary["sample_count"] > 0 else 0.35
        queue_penalty = min((summary["queue_depth_current"] or 0) / 4.0, 1.0)
        ttft_penalty = min((summary["ttft_ms_avg"] or 0.0) / 2500.0, 1.0)

        cpu_penalty = min(
            (hardware_status.get("cpu", {}).get("utilization_percent") or 0.0) / 100.0,
            1.0,
        )
        mem_penalty = min(
            (hardware_status.get("memory", {}).get("utilization_percent") or 0.0)
            / 100.0,
            1.0,
        )
        gpu_penalty = min(
            (hardware_status.get("gpu", {}).get("utilization_percent") or 0.0) / 100.0,
            1.0,
        )
        thermal_penalty = 1.0 if hardware_status.get("thermal_throttling") else 0.0

        score = (
            (quality_weight * benchmark_score)
            + (availability_weight * model_ready)
            + (privacy_weight * privacy_priority)
            - (0.25 * thermal_penalty)
            - (0.20 * max(cpu_penalty, mem_penalty, gpu_penalty))
            - (0.15 * queue_penalty)
            - (0.15 * ttft_penalty)
        )
        return round(max(0.0, min(score, 1.0)), 4)

    def recommend_downgrade(
        self,
        backend: str,
        available_backends: Sequence[str],
        hardware_status: Dict[str, Any],
        *,
        cloud_provider: Optional[str] = None,
        strict_local: bool = False,
        minimum_viability: float = 0.35,
    ) -> Dict[str, Any]:
        current_viability = self.local_viability(backend, hardware_status)
        should_downgrade = bool(
            hardware_status.get("should_offload")
            or current_viability < minimum_viability
        )
        if backend not in LOCAL_BACKENDS or not should_downgrade:
            return {
                "action": "keep",
                "target_provider": backend,
                "target_model": None,
                "current_viability": current_viability,
            }

        profile = self._backend_profiles.get(backend, {})
        candidate_backends = [
            candidate
            for candidate in profile.get("downgrade_backends", [])
            if candidate in available_backends
        ]
        if not candidate_backends:
            candidate_backends = [
                candidate
                for candidate in available_backends
                if candidate in LOCAL_BACKENDS and candidate != backend
            ]

        best_local = None
        best_score = -1.0
        for candidate in candidate_backends:
            score = self.local_viability(candidate, hardware_status)
            if score > best_score:
                best_score = score
                best_local = candidate

        if best_local and best_score >= minimum_viability:
            return {
                "action": "downgrade_local",
                "target_provider": best_local,
                "target_model": self._backend_profiles.get(best_local, {}).get(
                    "target_model"
                ),
                "current_viability": current_viability,
                "target_viability": best_score,
            }

        fallback_cloud = profile.get("cloud_fallback") or cloud_provider
        if not strict_local and fallback_cloud and fallback_cloud in available_backends:
            return {
                "action": "offload_cloud",
                "target_provider": fallback_cloud,
                "target_model": None,
                "current_viability": current_viability,
            }

        return {
            "action": "keep",
            "target_provider": backend,
            "target_model": None,
            "current_viability": current_viability,
        }

    def _summary_for_backend(self, backend: str) -> Dict[str, Any]:
        with self._lock:
            latencies = list(self._latencies.get(backend, []))
            ttft = list(self._ttft.get(backend, []))
            tokens = list(self._tokens_per_second.get(backend, []))
            queue_depth = list(self._queue_depth.get(backend, []))
            sources = list(self._sample_sources.get(backend, []))
            profile = dict(self._backend_profiles.get(backend, {}))
            pending = self._pending_requests.get(backend, 0)
            canary_count = self._canary_counts.get(backend, 0)
            last_sample_at = self._last_sample_at.get(backend)

        return {
            "pending_requests": pending,
            "queue_depth_current": (
                max(queue_depth[-1], pending) if queue_depth else pending
            ),
            "queue_depth_avg": _average(queue_depth),
            "sample_count": len(latencies),
            "canary_sample_count": canary_count,
            "latency_ms_avg": _average(latencies),
            "latency_ms_p95": _percentile(latencies, 95),
            "ttft_ms_avg": _average(ttft),
            "tokens_per_second_avg": _average(tokens),
            "tokens_per_second_ewma": _ewma(tokens),
            "latest_source": sources[-1] if sources else None,
            "last_sample_at": (
                round(last_sample_at, 4) if last_sample_at is not None else None
            ),
            "profile": profile,
        }

    def _ensure_sqlite(self) -> None:
        path = Path(self.sqlite_path or "")
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backend TEXT NOT NULL,
                    recorded_at REAL NOT NULL,
                    source TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    token_count INTEGER NOT NULL,
                    ttft_ms REAL,
                    tokens_per_second REAL,
                    queue_depth INTEGER,
                    metadata_json TEXT NOT NULL
                )
                """)
            connection.commit()

    def _persist_row(self, row: Dict[str, Any]) -> None:
        with sqlite3.connect(self.sqlite_path or "") as connection:
            connection.execute(
                """
                INSERT INTO benchmark_samples (
                    backend,
                    recorded_at,
                    source,
                    duration_ms,
                    token_count,
                    ttft_ms,
                    tokens_per_second,
                    queue_depth,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["backend"],
                    row["recorded_at"],
                    row["source"],
                    row["duration_ms"],
                    row["token_count"],
                    row["ttft_ms"],
                    row["tokens_per_second"],
                    row["queue_depth"],
                    json.dumps(row["metadata"], sort_keys=True),
                ),
            )
            connection.commit()


def _average(values: Sequence[float]) -> Optional[float]:
    return round(sum(values) / len(values), 4) if values else None


def _percentile(values: Sequence[float], percentile: int) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = max(
        0,
        min(len(ordered) - 1, math.ceil((percentile / 100.0) * len(ordered)) - 1),
    )
    return round(ordered[index], 4)


def _ewma(values: Sequence[float], alpha: float = 0.35) -> Optional[float]:
    if not values:
        return None
    current = values[0]
    for value in values[1:]:
        current = (alpha * value) + ((1 - alpha) * current)
    return round(current, 4)


__all__ = ["BenchmarkStore", "LOCAL_BACKENDS"]
