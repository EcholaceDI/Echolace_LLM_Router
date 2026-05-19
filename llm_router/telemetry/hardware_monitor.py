import importlib.util
import os
import platform
import re
import shutil
import subprocess
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional

from .benchmark_store import BenchmarkStore

CanaryRunner = Callable[[str, str], Any]


class HardwareMonitor:
    """
    Lightweight runtime monitor for local hardware conditions and canary benchmarks.
    """

    def __init__(
        self,
        history_size: int = 60,
        benchmark_store: Optional[BenchmarkStore] = None,
    ):
        self._history: Deque[Dict[str, Any]] = deque(maxlen=history_size)
        self.benchmark_store = benchmark_store or BenchmarkStore()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._canary_backends: Dict[str, Dict[str, Any]] = {}
        self._canary_lock = threading.RLock()

    def sample(self) -> Dict[str, Any]:
        metrics = {
            "timestamp": time.time(),
            "platform": platform.system(),
            "cpu": self._cpu_metrics(),
            "memory": self._memory_metrics(),
            "gpu": self._gpu_metrics(),
            "queue_depth": self.benchmark_store.pending_requests(),
        }
        metrics["thermal_throttling"] = self._thermal_throttling(metrics)
        metrics["should_offload"] = self._should_offload(metrics)
        self._history.append(metrics)
        return metrics

    def current(self) -> Dict[str, Any]:
        return self._history[-1] if self._history else self.sample()

    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def start_background(
        self,
        interval_seconds: int = 5,
        *,
        run_canaries: bool = True,
    ) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()

        def _runner() -> None:
            while not self._stop_event.is_set():
                self.sample()
                if run_canaries:
                    self.run_due_canaries()
                self._stop_event.wait(interval_seconds)

        self._thread = threading.Thread(target=_runner, daemon=True)
        self._thread.start()

    def stop_background(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._thread = None

    def register_canary_backend(
        self,
        backend: str,
        runner: CanaryRunner,
        *,
        prompt: str = "Respond with the word ok.",
        interval_seconds: int = 60,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._canary_lock:
            self._canary_backends[backend] = {
                "runner": runner,
                "prompt": prompt,
                "interval_seconds": interval_seconds,
                "metadata": metadata or {},
                "last_run_at": None,
            }

    def run_due_canaries(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        now = now or time.time()
        results: List[Dict[str, Any]] = []
        with self._canary_lock:
            backends = list(self._canary_backends.items())

        for backend, config in backends:
            last_run_at = config.get("last_run_at")
            interval_seconds = int(config.get("interval_seconds", 60))
            if last_run_at is not None and (now - last_run_at) < interval_seconds:
                continue
            result = self.run_canary_once(backend, now=now)
            results.append(result)
        return results

    def run_canary_once(
        self,
        backend: str,
        *,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        now = now or time.time()
        with self._canary_lock:
            config = dict(self._canary_backends[backend])
            self._canary_backends[backend]["last_run_at"] = now

        runner = config["runner"]
        prompt = config["prompt"]
        started_at = time.perf_counter()
        ttft_ms: Optional[float] = None
        token_count = 0
        response = ""
        try:
            outcome = runner(backend, prompt)
        except Exception as exc:
            duration_ms = (time.perf_counter() - started_at) * 1000.0
            row = self.benchmark_store.record_benchmark_sample(
                backend=backend,
                duration_ms=duration_ms,
                token_count=0,
                ttft_ms=duration_ms,
                queue_depth=self.benchmark_store.pending_requests(backend),
                source="canary",
                metadata={
                    **config.get("metadata", {}),
                    "error": str(exc),
                    "status": "failed",
                },
                recorded_at=now,
            )
            row["status"] = "failed"
            return row

        duration_ms = (time.perf_counter() - started_at) * 1000.0
        if isinstance(outcome, dict):
            response = str(outcome.get("response", ""))
            ttft_ms = outcome.get("ttft_ms")
            token_count = int(outcome.get("token_count") or _token_count(response))
            duration_ms = float(outcome.get("duration_ms", duration_ms))
        else:
            response = str(outcome)
            token_count = _token_count(response)

        if ttft_ms is None:
            ttft_ms = min(duration_ms, max(1.0, duration_ms * 0.6))

        row = self.benchmark_store.record_benchmark_sample(
            backend=backend,
            duration_ms=duration_ms,
            token_count=token_count,
            ttft_ms=ttft_ms,
            queue_depth=self.benchmark_store.pending_requests(backend),
            source="canary",
            metadata={
                **config.get("metadata", {}),
                "prompt": prompt,
                "status": "ok",
            },
            recorded_at=now,
        )
        row["status"] = "ok"
        return row

    def local_viability(self, backend: str, privacy_priority: float = 0.0) -> float:
        return self.benchmark_store.local_viability(
            backend,
            self.current(),
            privacy_priority=privacy_priority,
        )

    def downgrade_decision(
        self,
        backend: str,
        available_backends: List[str],
        *,
        cloud_provider: Optional[str] = None,
        strict_local: bool = False,
        minimum_viability: float = 0.35,
    ) -> Dict[str, Any]:
        return self.benchmark_store.recommend_downgrade(
            backend,
            available_backends,
            self.current(),
            cloud_provider=cloud_provider,
            strict_local=strict_local,
            minimum_viability=minimum_viability,
        )

    def _cpu_metrics(self) -> Dict[str, Any]:
        if importlib.util.find_spec("psutil") is None:
            return {
                "available": False,
                "utilization_percent": None,
                "frequency_current_mhz": None,
                "frequency_max_mhz": None,
            }

        import psutil

        freq = psutil.cpu_freq()
        return {
            "available": True,
            "utilization_percent": psutil.cpu_percent(interval=0.0),
            "frequency_current_mhz": getattr(freq, "current", None),
            "frequency_max_mhz": getattr(freq, "max", None),
            "load_average": os.getloadavg() if hasattr(os, "getloadavg") else None,
        }

    def _memory_metrics(self) -> Dict[str, Any]:
        if importlib.util.find_spec("psutil") is None:
            return {
                "available": False,
                "utilization_percent": None,
                "swap_percent": None,
            }

        import psutil

        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "available": True,
            "utilization_percent": vm.percent,
            "available_bytes": vm.available,
            "total_bytes": vm.total,
            "swap_percent": swap.percent,
        }

    def _gpu_metrics(self) -> Dict[str, Any]:
        metrics = {
            "available": False,
            "vendor": None,
            "cuda": False,
            "mps": False,
            "utilization_percent": None,
            "memory_utilization_percent": None,
            "temperature_c": None,
            "thermal_pressure": None,
        }

        torch_metrics = self._torch_gpu_metrics()
        metrics.update(torch_metrics)

        nvidia_metrics = self._nvidia_metrics()
        if nvidia_metrics:
            metrics.update(nvidia_metrics)
            return metrics

        amd_metrics = self._amd_metrics()
        if amd_metrics:
            metrics.update(amd_metrics)
            return metrics

        apple_metrics = self._apple_metrics()
        if apple_metrics:
            metrics.update(apple_metrics)
        return metrics

    def _torch_gpu_metrics(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        if importlib.util.find_spec("torch") is None:
            return metrics

        import torch

        metrics["cuda"] = torch.cuda.is_available()
        metrics["mps"] = bool(
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        )
        if metrics["cuda"]:
            metrics["available"] = True
            metrics["vendor"] = "nvidia"
            try:
                total = float(torch.cuda.get_device_properties(0).total_memory)
                used = float(torch.cuda.memory_allocated(0))
                metrics["memory_utilization_percent"] = round((used / total) * 100.0, 2)
            except Exception:
                pass
        elif metrics["mps"]:
            metrics["available"] = True
            metrics["vendor"] = "apple"
        return metrics

    def _nvidia_metrics(self) -> Optional[Dict[str, Any]]:
        if not shutil.which("nvidia-smi"):
            return None
        try:
            command = [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,utilization.memory,temperature.gpu",
                "--format=csv,noheader,nounits",
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
            line = result.stdout.strip().splitlines()[0]
            gpu_util, mem_util, temp_c = [part.strip() for part in line.split(",")]
            return {
                "available": True,
                "vendor": "nvidia",
                "utilization_percent": float(gpu_util),
                "memory_utilization_percent": float(mem_util),
                "temperature_c": float(temp_c),
            }
        except Exception:
            return None

    def _amd_metrics(self) -> Optional[Dict[str, Any]]:
        executable = shutil.which("rocm-smi")
        if not executable:
            return None
        try:
            result = subprocess.run(
                [executable, "--showuse", "--showtemp", "--showmemuse"],
                capture_output=True,
                text=True,
                check=False,
            )
            output = result.stdout
            util_match = re.search(r"GPU use.*?(\d+)%", output)
            mem_match = re.search(r"GPU memory use.*?(\d+)%", output)
            temp_match = re.search(r"Temperature.*?(\d+\.?\d*)c", output, re.IGNORECASE)
            return {
                "available": True,
                "vendor": "amd",
                "utilization_percent": (
                    float(util_match.group(1)) if util_match else None
                ),
                "memory_utilization_percent": (
                    float(mem_match.group(1)) if mem_match else None
                ),
                "temperature_c": float(temp_match.group(1)) if temp_match else None,
            }
        except Exception:
            return None

    def _apple_metrics(self) -> Optional[Dict[str, Any]]:
        if platform.system() != "Darwin":
            return None

        metrics: Dict[str, Any] = {
            "available": True,
            "vendor": "apple",
        }
        if shutil.which("pmset"):
            try:
                result = subprocess.run(
                    ["pmset", "-g", "therm"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                metrics["thermal_pressure"] = _parse_apple_thermal_pressure(
                    result.stdout
                )
            except Exception:
                pass
        if shutil.which("powermetrics"):
            metrics["powermetrics_available"] = True
        return metrics

    def _thermal_throttling(self, metrics: Dict[str, Any]) -> bool:
        gpu_temp = metrics["gpu"].get("temperature_c")
        if gpu_temp is not None and gpu_temp >= 85:
            return True

        thermal_pressure = metrics["gpu"].get("thermal_pressure")
        if thermal_pressure in {"serious", "critical"}:
            return True

        cpu = metrics["cpu"]
        utilization = cpu.get("utilization_percent")
        current = cpu.get("frequency_current_mhz")
        maximum = cpu.get("frequency_max_mhz")
        if (
            utilization is not None
            and current
            and maximum
            and maximum > 0
            and utilization >= 80
            and (float(current) / float(maximum)) < 0.7
        ):
            return True

        if importlib.util.find_spec("psutil") is not None:
            import psutil

            if hasattr(psutil, "sensors_temperatures"):
                try:
                    temps = psutil.sensors_temperatures()
                    for entries in temps.values():
                        for entry in entries:
                            current_temp = getattr(entry, "current", None)
                            if current_temp is not None and current_temp >= 90:
                                return True
                except Exception:
                    pass

        return False

    def _should_offload(self, metrics: Dict[str, Any]) -> bool:
        cpu_util = metrics["cpu"].get("utilization_percent") or 0.0
        mem_util = metrics["memory"].get("utilization_percent") or 0.0
        gpu_util = metrics["gpu"].get("utilization_percent")
        gpu_mem = metrics["gpu"].get("memory_utilization_percent")
        queue_depths = metrics.get("queue_depth", {})
        queue_pressure = max(queue_depths.values()) if queue_depths else 0
        return bool(
            cpu_util >= 90.0
            or mem_util >= 90.0
            or (gpu_util is not None and gpu_util >= 90.0)
            or (gpu_mem is not None and gpu_mem >= 90.0)
            or queue_pressure >= 4
            or metrics.get("thermal_throttling")
        )


def _parse_apple_thermal_pressure(output: str) -> Optional[str]:
    if not output:
        return None
    lowered = output.lower()
    for label in ("nominal", "moderate", "heavy", "serious", "critical"):
        if label in lowered:
            return label
    return None


def _token_count(text: str) -> int:
    return len(text.split()) if text else 0


__all__ = ["HardwareMonitor"]
