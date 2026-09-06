import os
import psutil
from typing import Dict, Any


def get_system_resource_metrics() -> Dict[str, Any]:
    """Captures CPU %, Memory usage (MB), and system thread count."""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    cpu_percent = process.cpu_percent(interval=0.1)

    system_mem = psutil.virtual_memory()

    return {
        "benchmark": "system_resources",
        "process_id": os.getpid(),
        "cpu_percent": cpu_percent,
        "memory_rss_mb": round(mem_info.rss / (1024 * 1024), 2),
        "memory_vms_mb": round(mem_info.vms / (1024 * 1024), 2),
        "system_total_ram_gb": round(system_mem.total / (1024 ** 3), 2),
        "system_available_ram_gb": round(system_mem.available / (1024 ** 3), 2),
        "system_ram_usage_percent": system_mem.percent,
        "num_threads": process.num_threads()
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_system_resource_metrics(), indent=2))
