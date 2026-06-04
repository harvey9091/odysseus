# services/scraper/resource_manager — Server resource protection for scraping
"""Resource management for scraper to prevent server overload.

Protects against:
- CPU overload (>80%)
- RAM overload (>75%)  
- Browser instance proliferation
- Request rate issues
"""

import asyncio
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# Resource thresholds (percentages)
CPU_THRESHOLD = 80.0
RAM_THRESHOLD = 75.0

# Concurrency limits
MAX_WORKERS = 5
MAX_BROWSER_INSTANCES = 3

# Rate limiting (requests per second)
REQUESTS_PER_SECOND = 2


class SystemLoadState(Enum):
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QueuedJob:
    run_id: str
    source_url: str
    owner: str
    queued_at: float = field(default_factory=time.time)
    retry_count: int = 0


class ResourceManager:
    """Manages scraper resources with strict limits to protect server stability."""

    def __init__(self):
        self._workers_semaphore = asyncio.Semaphore(MAX_WORKERS)
        self._browser_semaphore = asyncio.Semaphore(MAX_BROWSER_INSTANCES)
        self._active_workers = 0
        self._browser_instances = 0
        self._request_times: deque = deque(maxlen=100)
        self._load_state = SystemLoadState.NORMAL
        self._consecutive_high_load = 0
        self._paused_until: Optional[float] = None
        self._job_queue: list[QueuedJob] = []
        self._queue_event = asyncio.Event()
        self._queue_event.set()

    async def acquire_worker(self, timeout: float = 300.0) -> bool:
        """Acquire a worker slot. Returns False if server is overloaded or paused."""
        if not await self._check_load_state():
            return False

        try:
            await asyncio.wait_for(self._workers_semaphore.acquire(), timeout=timeout)
            self._active_workers += 1
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Worker acquisition timed out after {timeout}s - server may be overloaded")
            return False

    def release_worker(self):
        """Release a worker slot."""
        self._active_workers = max(0, self._active_workers - 1)
        self._workers_semaphore.release()

    async def acquire_browser(self, timeout: float = 60.0) -> bool:
        """Acquire a browser instance slot."""
        try:
            await asyncio.wait_for(self._browser_semaphore.acquire(), timeout=timeout)
            self._browser_instances += 1
            return True
        except asyncio.TimeoutError:
            logger.warning("Browser instance acquisition timed out - max concurrent browsers reached")
            return False

    def release_browser(self):
        """Release a browser instance slot."""
        self._browser_instances = max(0, self._browser_instances - 1)
        self._browser_semaphore.release()

    async def rate_limit(self):
        """Enforce rate limiting on requests."""
        now = time.time()
        self._request_times.append(now)

        min_interval = 1.0 / REQUESTS_PER_SECOND
        while len(self._request_times) >= 2:
            time_diff = now - self._request_times[0]
            if time_diff < min_interval:
                sleep_time = min_interval - time_diff
                await asyncio.sleep(sleep_time)
                now = time.time()
                self._request_times.append(now)
            else:
                break

    def queue_job(self, run_id: str, source_url: str, owner: str) -> bool:
        """Queue a job for later execution. Returns True if queued (not rejected)."""
        if self._load_state == SystemLoadState.CRITICAL:
            logger.error(f"Rejecting scrape job {run_id} - system in critical state")
            return False

        self._job_queue.append(QueuedJob(run_id=run_id, source_url=source_url, owner=owner))
        self._queue_event.set()
        logger.info(f"Queued scrape job {run_id} (queue size: {len(self._job_queue)})")
        return True

    def get_queued_job(self) -> Optional[QueuedJob]:
        """Get next queued job, or None if empty."""
        if self._job_queue:
            return self._job_queue.pop(0)
        return None

    def queue_size(self) -> int:
        """Return current queue size."""
        return len(self._job_queue)

    async def _check_load_state(self) -> bool:
        """Check system load and return True if scraping should proceed."""
        if self._paused_until and time.time() < self._paused_until:
            return False

        self._paused_until = None
        cpu = await self._get_cpu_percent()
        ram = await self._get_ram_percent()

        if cpu >= CPU_THRESHOLD or ram >= RAM_THRESHOLD:
            self._consecutive_high_load += 1
            if self._consecutive_high_load >= 3:
                self._load_state = SystemLoadState.CRITICAL
                self._paused_until = time.time() + 60
                logger.warning(f"CRITICAL load detected (CPU: {cpu:.1f}%, RAM: {ram:.1f}%) - pausing scraping for 60s")
            elif self._consecutive_high_load >= 2:
                self._load_state = SystemLoadState.HIGH
                logger.warning(f"High load detected (CPU: {cpu:.1f}%, RAM: {ram:.1f}%)")
            return False
        else:
            self._consecutive_high_load = 0
            self._load_state = SystemLoadState.NORMAL
            return True

    @staticmethod
    def _get_cpu_percent_sync() -> float:
        """Get CPU usage percentage (sync version for health_check)."""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except ImportError:
            try:
                with open("/proc/loadavg") as f:
                    load = float(f.read().split()[0])
                return min(load * 100 / os.cpu_count(), 100) if os.cpu_count() else 50
            except Exception:
                return 50.0

    @staticmethod
    async def _get_cpu_percent() -> float:
        """Get CPU usage percentage."""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except ImportError:
            try:
                with open("/proc/loadavg") as f:
                    load = float(f.read().split()[0])
                return min(load * 100 / os.cpu_count(), 100) if os.cpu_count() else 50
            except Exception:
                return 50.0

    @staticmethod
    def _get_ram_percent_sync() -> float:
        """Get RAM usage percentage (sync version for health_check)."""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            try:
                with open("/proc/meminfo") as f:
                    lines = f.readlines()
                    mem_total = int(lines[0].split()[1])
                    mem_available = int(lines[6].split()[1])
                    return 100 - (mem_available / mem_total * 100)
            except Exception:
                return 50.0

    @staticmethod
    async def _get_ram_percent() -> float:
        """Get RAM usage percentage."""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            try:
                with open("/proc/meminfo") as f:
                    lines = f.readlines()
                    mem_total = int(lines[0].split()[1])
                    mem_available = int(lines[6].split()[1])
                    return 100 - (mem_available / mem_total * 100)
            except Exception:
                return 50.0

    def get_status(self) -> dict:
        """Get current resource manager status."""
        return {
            "active_workers": self._active_workers,
            "max_workers": MAX_WORKERS,
            "browser_instances": self._browser_instances,
            "max_browser_instances": MAX_BROWSER_INSTANCES,
            "load_state": self._load_state.value,
            "queue_size": self.queue_size(),
            "requests_per_second": REQUESTS_PER_SECOND,
            "paused_until": self._paused_until,
        }

    def health_check(self) -> dict:
        """Comprehensive health check in cloud-friendly format."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
        except ImportError:
            cpu = self._get_cpu_percent_sync()
            ram = self._get_ram_percent_sync()
            disk = 50.0

        status = self.get_status()
        status.update({
            "cpu_percent": cpu,
            "ram_percent": ram,
            "disk_percent": disk,
            "healthy": cpu < CPU_THRESHOLD and ram < RAM_THRESHOLD,
            "can_accept_jobs": self._load_state != SystemLoadState.CRITICAL and self.queue_size() < 100,
        })

        if cpu >= CPU_THRESHOLD:
            logger.warning(f"Health alert: CPU usage {cpu:.1f}% exceeds threshold {CPU_THRESHOLD}%")
        if ram >= RAM_THRESHOLD:
            logger.warning(f"Health alert: RAM usage {ram:.1f}% exceeds threshold {RAM_THRESHOLD}%")

        return status


# Global singleton instance
_resource_manager: Optional["ResourceManager"] = None


def get_resource_manager() -> ResourceManager:
    """Get or create the global resource manager."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager