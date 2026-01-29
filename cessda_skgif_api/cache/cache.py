# Copyright CESSDA ERIC 2026
# Copyright Finnish Social Science Data Archive FSD / University of Tampere 2026

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import time
import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class AsyncTTLCache:
    """
    Soft-expiring async TTL cache with grouped timestamps:

    - Never clears the entire cache automatically.
    - Always appends/fetches a missing key (even if cache is "fresh").
    - Refreshes the requested key when its group's timestamp has elapsed.
    - Persists to disk: entries + per-group timestamps.
    - Sync accessor returns RAM-only (stale or fresh), no I/O.

    Disk layout (JSON):
    {
      "entries": { "<key>": <value>, ... },
      "groups_ts": { "<group>": <unix_ts>, ... }
    }
    """

    def __init__(
        self,
        cache_file: Path,
        ttl_seconds: int = 24 * 3600,
        group_fn: Optional[Callable[[str], str]] = None,
    ):
        self.cache_file = cache_file
        self.ttl = ttl_seconds
        # Decide which group a key belongs to:
        # - If None: default to the key itself (per-key freshness)
        self.group_fn = group_fn or (lambda k: k)

        # In-memory state
        self._entries: Dict[str, Any] = {}
        self._groups_ts: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    # ---------- Persistence ----------
    def load_from_disk(self) -> None:
        if not self.cache_file.exists():
            return
        try:
            raw = json.loads(self.cache_file.read_text())
            if isinstance(raw, dict):
                self._entries = raw.get("entries", {}) or {}
                self._groups_ts = raw.get("groups_ts", {}) or {}
        except (OSError, json.JSONDecodeError) as e:
            print(f"[Cache] Error loading disk cache: {e}")

    def save_to_disk(self) -> None:
        try:
            payload = {
                "entries": self._entries,
                "groups_ts": self._groups_ts,
            }
            self.cache_file.write_text(json.dumps(payload))
        except (OSError, TypeError, ValueError) as e:
            print(f"[Cache] Error saving disk cache: {e}")

    # ---------- Main async accessor ----------
    async def get(self, key: str, fetcher: Callable[[str], Any]) -> Any:
        """
        Return cached entry for `key`.

        - If key is present and group's TTL not expired -> return current value.
        - If key is missing -> fetch and append (always).
        - If group's TTL expired -> re-fetch the requested key, overwrite, update group's timestamp.
        """
        async with self._lock:
            now = time.time()
            group = self.group_fn(key)
            group_ts = float(self._groups_ts.get(group, 0.0))
            group_expired = (now - group_ts) > self.ttl

            has_key = key in self._entries

            if has_key and not group_expired:
                # Fresh enough for this group: return current value
                return self._entries[key]

            # Missing OR group expired: fetch and store this key
            value = await fetcher(key)
            self._entries[key] = value
            # Bump the group's timestamp to "now"
            self._groups_ts[group] = now
            self.save_to_disk()
            return value

    async def preload(self, keys: list[str], fetcher: Callable[[str], Any]) -> None:
        """
        Warm the cache:
          - Load existing entries from disk
          - Ensure the provided keys exist (fetch as needed)
        """
        self.load_from_disk()
        for k in keys:
            await self.get(k, fetcher)

    # ---------- Sync, in-memory read ----------
    def get_in_memory(self, key: str):
        """
        Synchronous, read-only access to whatever is currently in RAM.
        """
        return self._entries.get(key)
