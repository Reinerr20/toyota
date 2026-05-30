import logging
import threading
import sqlite3
import queue
import time
import re
import base64
import os
import cv2
import numpy as np
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from src.api_client.api_service import ApiService
from src.api_client.event import DrowsinessEvent as ApiEvent
from src.api_client import config

log = logging.getLogger(__name__)

@dataclass
class _RemoteSendResult:
    success: bool
    status_code: int = 0
    error: str = ""

class RemoteLogWorker:
    RETRY_INTERVAL_SEC = 30
    MAX_QUEUE_SIZE = 100
    SEND_BATCH_SIZE = 5
    IMAGE_MAX_WIDTH = 480
    IMAGE_JPEG_QUALITY = 60

    def __init__(self, db_path: str, remote_api_url: Optional[str] = None, enabled: bool = True, require_image: bool = False):
        """
        db_path: path to the MAIN DB (contains users + events).
        require_image: if True, do not send events without an image. For "events-only", keep False.
        """
        self.enabled = enabled
        self.require_image = require_image
        self.include_image = self._env_bool("DS_REMOTE_INCLUDE_IMAGE", default=False)
        self._db_lock = threading.Lock()

        target_base_url = remote_api_url if remote_api_url else config.SERVER_BASE_URL
        self.api_service = ApiService(base_url=target_base_url) if enabled else None
        if self.api_service:
            log.info(f"[REMOTE] Worker started (Base: {target_base_url})")
        else:
            log.info("[REMOTE] Worker disabled")

        # MAIN DB connection (read local events/images from here)
        self.events_conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
        self._ensure_remote_columns()

        unsent_count = self._count_unsent_events()
        mode = "event+image" if self.include_image else "event-only"
        log.info("[REMOTE] include_image=%s (DS_REMOTE_INCLUDE_IMAGE=%s)", self.include_image, int(self.include_image))
        log.info("[REMOTE] Unsent events: %d", unsent_count)
        log.info("[REMOTE] Remote sync mode: %s, batch_size=%d, retry_interval=%ss", mode, self.SEND_BATCH_SIZE, self.RETRY_INTERVAL_SEC)

        self._immediate_q: "queue.Queue[tuple]" = queue.Queue(maxsize=200)
        self._stop_event = threading.Event()

        self._retry_thread = None
        self._send_thread = None
        if self.enabled and self.api_service:
            self._send_thread = threading.Thread(target=self._send_loop, daemon=True)
            self._send_thread.start()
            self._retry_thread = threading.Thread(target=self._retry_loop, daemon=True)
            self._retry_thread.start()

    @staticmethod
    def _env_bool(name: str, default: bool = False) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _ensure_remote_columns(self) -> None:
        """Keep remote outbox columns available even for older DB files."""
        try:
            with self._db_lock:
                cur = self.events_conn.cursor()
                cur.execute("PRAGMA table_info(events)")
                cols = {row[1] for row in cur.fetchall()}
                if "delivery_status" not in cols:
                    cur.execute("ALTER TABLE events ADD COLUMN delivery_status TEXT DEFAULT 'new'")
                    cols.add("delivery_status")
                if "remote_sent" not in cols:
                    cur.execute("ALTER TABLE events ADD COLUMN remote_sent INTEGER DEFAULT 0")
                if "remote_sent_at" not in cols:
                    cur.execute("ALTER TABLE events ADD COLUMN remote_sent_at TEXT NULL")
                if "remote_attempts" not in cols:
                    cur.execute("ALTER TABLE events ADD COLUMN remote_attempts INTEGER DEFAULT 0")
                if "remote_last_error" not in cols:
                    cur.execute("ALTER TABLE events ADD COLUMN remote_last_error TEXT NULL")
                if "delivery_status" in cols:
                    cur.execute(
                        """
                        UPDATE events
                        SET delivery_status = 'pending'
                        WHERE COALESCE(remote_sent, 0) = 0
                          AND delivery_status = 'queued'
                        """
                    )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_events_remote_sent ON events(remote_sent, id)")
                self.events_conn.commit()
        except Exception as e:
            log.error("[REMOTE] Failed to ensure remote columns: %s", e, exc_info=True)

    def _count_unsent_events(self) -> int:
        try:
            with self._db_lock:
                row = self.events_conn.execute(
                    "SELECT COUNT(*) FROM events WHERE COALESCE(remote_sent, 0) = 0"
                ).fetchone()
            return int(row[0]) if row else 0
        except Exception as e:
            log.warning("[REMOTE] Could not count unsent events: %s", e)
            return 0

    @staticmethod
    def _coerce_datetime(value) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    pass
        return datetime.now()

    def send_or_queue(
        self,
        vehicle_vin: str,
        user_id: int,
        status: str,
        time_dt: datetime,
        raw_jpeg: Optional[bytes],
        alert_category: Optional[str] = None,
        alert_detail: Optional[str] = None,
        severity: Optional[str] = None,
        local_event_id: Optional[int] = None,
        duration: Optional[float] = None,
        value: Optional[float] = None,
    ):
        """Push into immediate queue with new management fields."""
        if not (self.enabled and self.api_service):
            return
        try:
            self._mark_remote_queued(local_event_id)
            self._immediate_q.put_nowait(
                (
                    vehicle_vin,
                    user_id,
                    status,
                    time_dt,
                    raw_jpeg,
                    alert_category,
                    alert_detail,
                    severity,
                    local_event_id,
                    duration,
                    value,
                )
            )
        except queue.Full:
            log.warning("[REMOTE] Immediate queue full; marking pending in events")
            self._queue(
                vehicle_vin,
                user_id,
                status,
                time_dt,
                raw_jpeg,
                alert_category,
                alert_detail,
                severity,
                local_event_id,
            )

    def _mark_remote_queued(self, event_id: Optional[int]) -> None:
        if event_id is None or int(event_id) < 0:
            return
        try:
            with self._db_lock:
                self.events_conn.execute(
                    "UPDATE events SET delivery_status = ?, remote_sent = 0 WHERE id = ?",
                    ("queued", int(event_id)),
                )
                self.events_conn.commit()
        except Exception as e:
            log.warning("[REMOTE] Failed to mark event queued: event_id=%s error=%s", event_id, e)

    def _send_event(
        self,
        vin,
        uid,
        status,
        dt,
        jpeg_bytes,
        alert_category=None,
        alert_detail=None,
        severity=None,
        duration: Optional[float] = None,
        value: Optional[float] = None,
    ) -> _RemoteSendResult:
        attempted_with_image = bool(self.include_image and jpeg_bytes)
        result = self._post_event(
            vin,
            uid,
            status,
            dt,
            jpeg_bytes,
            alert_category=alert_category,
            alert_detail=alert_detail,
            severity=severity,
            duration=duration,
            value=value,
            include_image=self.include_image,
        )
        if result.status_code == 413 and attempted_with_image:
            log.warning("[REMOTE] HTTP 413, retrying event-only")
            event_only_result = self._post_event(
                vin,
                uid,
                status,
                dt,
                jpeg_bytes,
                alert_category=alert_category,
                alert_detail=alert_detail,
                severity=severity,
                duration=duration,
                value=value,
                include_image=False,
            )
            if not event_only_result.success:
                event_only_result.error = (
                    "HTTP 413 image payload too large; event-only retry failed: "
                    f"{event_only_result.error or 'remote send failed'}"
                )
            return event_only_result
        return result

    def _post_event(
        self,
        vin,
        uid,
        status,
        dt,
        jpeg_bytes,
        alert_category=None,
        alert_detail=None,
        severity=None,
        duration: Optional[float] = None,
        value: Optional[float] = None,
        include_image: bool = False,
    ) -> _RemoteSendResult:
        """Send to API; sanitize fields to avoid server-side 500s from null/bad values."""
        try:
            dt_obj = self._coerce_datetime(dt)

            # Sanitize status (remove spaces/special chars)
            norm_status = (status or "event").strip().lower()
            norm_status = re.sub(r"\s+", "_", norm_status)
            norm_status = re.sub(r"[^a-z0-9_]+", "_", norm_status)
            norm_status = re.sub(r"_+", "_", norm_status).strip("_")

            norm_cat = (alert_category.strip() if isinstance(alert_category, str) else alert_category)
            norm_detail = (alert_detail.strip() if isinstance(alert_detail, str) else alert_detail)
            norm_sev = (severity.strip() if isinstance(severity, str) else severity)

            remote_jpeg = self._prepare_remote_image(jpeg_bytes) if include_image else None

            # EVENTS-ONLY: allow sending without image
            if self.require_image and not remote_jpeg:
                log.warning(
                    "[REMOTE] Skip send (missing image; require_image=True): vin=%s uid=%s status=%r time=%s",
                    vin, uid, norm_status, dt_obj.isoformat()
                )
                return _RemoteSendResult(False, error="missing image")

            b64 = None
            if remote_jpeg:
                b64 = base64.b64encode(remote_jpeg).decode("ascii")

            event = ApiEvent(
                vehicle_identification_number=vin,
                user_id=uid,
                status=norm_status,
                time=dt_obj,
                img_drowsiness=b64,  # may be None (events-only)
                img_path=None,
            )

            # Optional fields (set only if server model supports them)
            if hasattr(event, "alert_category"):
                event.alert_category = norm_cat
            if hasattr(event, "alert_detail"):
                event.alert_detail = norm_detail
            if hasattr(event, "severity"):
                event.severity = norm_sev
            if hasattr(event, "duration") and duration is not None:
                event.duration = float(duration)
            if hasattr(event, "value") and value is not None:
                event.value = float(value)

            res = self.api_service.send_drowsiness_event(event)
            if getattr(res, "success", False):
                log.info("[REMOTE] ✓ Sent %s (CID: %s)", norm_cat or norm_status, getattr(res, "correlation_id", "-"))
                return _RemoteSendResult(True, status_code=int(getattr(res, "status_code", 0) or 0))

            log.warning(
                "[REMOTE] Send failed: error=%r status_code=%r vin=%s uid=%s status=%r time=%s",
                getattr(res, "error", "unknown error"),
                getattr(res, "status_code", None),
                vin, uid, norm_status, dt_obj.isoformat()
            )
            return _RemoteSendResult(
                False,
                status_code=int(getattr(res, "status_code", 0) or 0),
                error=str(getattr(res, "error", "unknown error") or "unknown error"),
            )
        except Exception as e:
            log.error("[REMOTE] Send exception: %s", e, exc_info=True)
            return _RemoteSendResult(False, error=str(e))

    def _prepare_remote_image(self, jpeg_bytes: Optional[bytes]) -> Optional[bytes]:
        if not jpeg_bytes:
            return None

        old_size = len(jpeg_bytes)
        try:
            arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                log.warning("[REMOTE] Could not decode image for compression; sending event-only")
                return None

            h, w = img.shape[:2]
            if w > self.IMAGE_MAX_WIDTH:
                scale = self.IMAGE_MAX_WIDTH / float(w)
                new_h = max(1, int(round(h * scale)))
                img = cv2.resize(img, (self.IMAGE_MAX_WIDTH, new_h), interpolation=cv2.INTER_AREA)

            ok, buf = cv2.imencode(
                ".jpg",
                img,
                [int(cv2.IMWRITE_JPEG_QUALITY), int(self.IMAGE_JPEG_QUALITY)],
            )
            if not ok:
                log.warning("[REMOTE] Could not encode compressed image; sending event-only")
                return None

            compressed = bytes(buf)
            log.info("[REMOTE] Compressed image bytes: old=%d compressed=%d", old_size, len(compressed))
            return compressed
        except Exception as e:
            log.warning("[REMOTE] Image compression failed; sending event-only: %s", e)
            return None

    def _queue(
        self,
        vin,
        uid,
        status,
        dt,
        jpeg_bytes,
        alert_category=None,
        alert_detail=None,
        severity=None,
        local_event_id: Optional[int] = None,
    ):
        """Use events table as the outbox (delivery_status=pending)."""
        if local_event_id is None:
            log.warning("[REMOTE] No local_event_id; cannot mark pending in events")
            return
        try:
            with self._db_lock:
                self.events_conn.execute(
                    "UPDATE events SET delivery_status = ?, remote_sent = 0 WHERE id = ?",
                    ("pending", int(local_event_id)),
                )
                self.events_conn.commit()
            log.info("[REMOTE] ⧖ Marked pending: event_id=%s", local_event_id)
        except Exception as e:
            log.error("[REMOTE] Queue error: %s", e, exc_info=True)

    def _mark_remote_sent(self, event_id: Optional[int]) -> None:
        if event_id is None or int(event_id) < 0:
            return
        try:
            with self._db_lock:
                self.events_conn.execute(
                    """
                    UPDATE events
                    SET remote_sent = 1,
                        remote_sent_at = ?,
                        remote_last_error = NULL,
                        delivery_status = ?
                    WHERE id = ?
                    """,
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "sent", int(event_id)),
                )
                self.events_conn.commit()
        except Exception as e:
            log.error("[REMOTE] Failed to mark event sent: event_id=%s error=%s", event_id, e, exc_info=True)

    def _mark_remote_failed(self, event_id: Optional[int], error: str) -> int:
        if event_id is None or int(event_id) < 0:
            return 0
        safe_error = (error or "remote send failed")[:500]
        try:
            with self._db_lock:
                self.events_conn.execute(
                    """
                    UPDATE events
                    SET remote_sent = 0,
                        remote_attempts = COALESCE(remote_attempts, 0) + 1,
                        remote_last_error = ?,
                        delivery_status = ?
                    WHERE id = ?
                    """,
                    (safe_error, "pending", int(event_id)),
                )
                row = self.events_conn.execute(
                    "SELECT COALESCE(remote_attempts, 0) FROM events WHERE id = ?",
                    (int(event_id),),
                ).fetchone()
                self.events_conn.commit()
            return int(row[0]) if row else 0
        except Exception as e:
            log.error("[REMOTE] Failed to mark event failed: event_id=%s error=%s", event_id, e, exc_info=True)
            return 0

    @staticmethod
    def _backoff_seconds(attempts: int) -> float:
        if attempts <= 0:
            return 0.0
        return float(min(300, 5 * (2 ** min(attempts - 1, 6))))

    def _sleep_with_stop(self, seconds: float) -> None:
        end = time.time() + max(0.0, seconds)
        while not self._stop_event.is_set() and time.time() < end:
            time.sleep(min(0.5, end - time.time()))

    def _fetch_local_jpeg(self, local_event_id: int) -> Optional[bytes]:
        """Fetch jpeg bytes from MAIN local events table."""
        with self._db_lock:
            row = self.events_conn.execute(
                "SELECT img_drowsiness FROM events WHERE id = ?",
                (int(local_event_id),),
            ).fetchone()
        return row[0] if row and row[0] else None

    def _process_queue(self):
        if not self.api_service:
            return

        with self._db_lock:
            rows = self.events_conn.execute(
                """
                SELECT id, vehicle_identification_number, user_id, time, status,
                       img_drowsiness, duration, value, alert_category, alert_detail, severity,
                       COALESCE(remote_attempts, 0), remote_last_error
                FROM events
                WHERE COALESCE(remote_sent, 0) = 0
                  AND COALESCE(delivery_status, 'new') != 'queued'
                ORDER BY id ASC
                LIMIT ?
                """,
                (self.SEND_BATCH_SIZE,),
            ).fetchall()

        for (eid, vin, uid, time_str, status, img_blob, duration,
             value, alert_category, alert_detail, severity, attempts, last_error) in rows:
            if self.include_image and last_error and "HTTP 413" in str(last_error):
                img_blob = None

            result = self._send_event(
                vin,
                uid,
                status,         # IMPORTANT: status is the event type (do not replace it)
                time_str,
                img_blob,
                alert_category=alert_category,
                alert_detail=alert_detail,
                severity=severity,
                duration=duration,
                value=value,
            )

            if result.success:
                with self._db_lock:
                    self.events_conn.execute(
                        """
                        UPDATE events
                        SET remote_sent = 1,
                            remote_sent_at = ?,
                            remote_last_error = NULL,
                            delivery_status = ?
                        WHERE id = ?
                        """,
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "sent", int(eid)),
                    )
                    self.events_conn.commit()
                    log.info("[REMOTE] ✓ Sent event_id=%s", eid)

            else:
                next_attempts = self._mark_remote_failed(eid, result.error or f"HTTP {result.status_code}")
                backoff = self._backoff_seconds(next_attempts or attempts + 1)
                log.warning("[REMOTE] Backing off %.0fs after event_id=%s failure", backoff, eid)
                self._sleep_with_stop(backoff)

    def _send_loop(self) -> None:
        """Drain immediate queue; if jpeg missing, try rehydrate from local DB before sending."""
        while not self._stop_event.is_set():
            try:
                item = self._immediate_q.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                (
                    vin,
                    uid,
                    status,
                    dt,
                    jpeg_bytes,
                    alert_category,
                    alert_detail,
                    severity,
                    local_event_id,
                    duration,
                    value,
                ) = item

                if not jpeg_bytes and local_event_id:
                    jpeg_bytes = self._fetch_local_jpeg(local_event_id)

                result = self._send_event(
                    vin,
                    uid,
                    status,
                    dt,
                    jpeg_bytes,
                    alert_category=alert_category,
                    alert_detail=alert_detail,
                    severity=severity,
                    duration=duration,
                    value=value,
                )
                if result.success:
                    self._mark_remote_sent(local_event_id)
                else:
                    attempts = self._mark_remote_failed(
                        local_event_id,
                        result.error or f"HTTP {result.status_code}",
                    )
                    self._queue(vin, uid, status, dt, jpeg_bytes, alert_category, alert_detail, severity, local_event_id)
                    backoff = self._backoff_seconds(attempts)
                    if backoff:
                        log.warning("[REMOTE] Backing off %.0fs after immediate send failure", backoff)
                        self._sleep_with_stop(backoff)
            except Exception as e:
                log.error("[REMOTE] Send loop error: %s", e, exc_info=True)
            finally:
                try:
                    self._immediate_q.task_done()
                except Exception:
                    pass

    def _retry_loop(self) -> None:
        """Periodically retry sending pending rows from events table."""
        while not self._stop_event.is_set():
            try:
                self._process_queue()
            except Exception as e:
                log.error("[REMOTE] Retry loop error: %s", e, exc_info=True)

            # Sleep in small increments so shutdown is responsive
            for _ in range(int(self.RETRY_INTERVAL_SEC * 10)):
                if self._stop_event.is_set():
                    break
                time.sleep(0.1)

    def close(self):
        self._stop_event.set()
        if self._send_thread:
            self._send_thread.join()
        if self._retry_thread:
            self._retry_thread.join()
        self.events_conn.close()
        log.info("[REMOTE] Worker stopped")
