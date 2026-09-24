import subprocess
import threading
import time

import psutil

GIB = 1024 ** 3


def command(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10, check=False).stdout
    except Exception as exc:
        return str(exc)


def snapshot(torch=None, commands=False):
    mem, swap = psutil.virtual_memory(), psutil.swap_memory()
    result = {"timestamp": time.time(), "system_total_bytes": mem.total, "system_used_bytes": mem.used,
              "system_available_bytes": mem.available, "swap_used_bytes": swap.used,
              "process_rss_bytes": psutil.Process().memory_info().rss}
    if torch is not None and torch.cuda.is_initialized():
        result.update(cuda_allocated_bytes=torch.cuda.memory_allocated(), cuda_reserved_bytes=torch.cuda.memory_reserved(),
                      cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(), cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved())
    if commands:
        result.update(free_h=command(["free", "-h"]), nvidia_smi=command(["nvidia-smi"]),
                      vllm_processes=[{"pid": p.pid, "created": p.create_time(), "name": p.name()}
                                      for p in psutil.process_iter() if p.name().startswith("VLLM::EngineCo")])
    return result


def guard(min_available_gib=8, swap_baseline=None):
    state = snapshot()
    if state["system_available_bytes"] < min_available_gib * GIB:
        raise MemoryError(f"Insufficient unified memory: {state['system_available_bytes'] / GIB:.2f} GiB available; {min_available_gib} GiB required. Existing vLLM left untouched.")
    if swap_baseline is not None and state["swap_used_bytes"] - swap_baseline > .25 * GIB:
        raise MemoryError("Swap usage grew by more than 256 MiB; stopping router work. Existing vLLM left untouched.")


class Monitor:
    def __init__(self, torch):
        self.torch = torch
        self.samples = []
        self.stop_event = threading.Event()

    def start(self):
        self.torch.cuda.reset_peak_memory_stats()
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.thread.start()
        return self

    def _sample(self):
        while not self.stop_event.is_set():
            self.samples.append(snapshot())
            self.stop_event.wait(.25)

    def stop(self):
        self.stop_event.set()
        self.thread.join()
        self.samples.append(snapshot(self.torch))
        return {"interval_seconds": .25, "min_available_bytes": min(s["system_available_bytes"] for s in self.samples),
                "max_used_bytes": max(s["system_used_bytes"] for s in self.samples),
                "max_swap_used_bytes": max(s["swap_used_bytes"] for s in self.samples),
                "cuda_peak_allocated_bytes": self.torch.cuda.max_memory_allocated(),
                "cuda_peak_reserved_bytes": self.torch.cuda.max_memory_reserved(), "samples": self.samples}
