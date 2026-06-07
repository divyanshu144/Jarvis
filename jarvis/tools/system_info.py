"""System information — battery, wifi, CPU, memory."""

from __future__ import annotations

from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "system_info",
    "description": "Get current system stats: battery level, wifi network, CPU usage, memory usage.",
    "input_schema": {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": ["all", "battery", "wifi", "cpu", "memory", "disk"],
                "description": "Which metric to retrieve.",
            }
        },
        "required": ["metric"],
    },
}


def execute(metric: str = "all") -> str:
    import psutil
    import subprocess

    results: list[str] = []

    def _battery() -> str:
        b = psutil.sensors_battery()
        if b is None:
            return "Battery: N/A (desktop?)"
        plugged = "charging" if b.power_plugged else "on battery"
        return f"Battery: {b.percent:.0f}% ({plugged})"

    def _wifi() -> str:
        try:
            r = subprocess.run(
                ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
                capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.splitlines():
                if " SSID:" in line:
                    return f"WiFi: {line.split('SSID:')[1].strip()}"
            return "WiFi: not connected"
        except Exception:
            return "WiFi: unable to read"

    def _cpu() -> str:
        pct = psutil.cpu_percent(interval=0.5)
        cores = psutil.cpu_count()
        freq = psutil.cpu_freq()
        ghz = f"{freq.current / 1000:.2f} GHz" if freq else ""
        return f"CPU: {pct}% usage, {cores} cores {ghz}"

    def _memory() -> str:
        m = psutil.virtual_memory()
        used = m.used / 1e9
        total = m.total / 1e9
        return f"Memory: {used:.1f} GB / {total:.1f} GB ({m.percent}% used)"

    def _disk() -> str:
        d = psutil.disk_usage("/")
        free = d.free / 1e9
        total = d.total / 1e9
        return f"Disk: {free:.1f} GB free / {total:.1f} GB total"

    try:
        if metric in ("all", "battery"):
            results.append(_battery())
        if metric in ("all", "wifi"):
            results.append(_wifi())
        if metric in ("all", "cpu"):
            results.append(_cpu())
        if metric in ("all", "memory"):
            results.append(_memory())
        if metric in ("all", "disk"):
            results.append(_disk())
        return "\n".join(results)
    except Exception as e:
        log.error(f"system_info failed: {e}")
        return f"Error: {e}"
