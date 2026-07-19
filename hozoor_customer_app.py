# -*- coding: utf-8 -*-
"""
HiMate Sync - Customer Final Installer
Version: CUSTOMER-FINAL-INSTALLER-0.4.2

Rules:
- Customer UI is clean and product-facing, not debug-facing.
- One active device is handled at a time.
- App is server-bound to the central HiMate VPS, not device-bound.
- device_code is read from hardware and Laravel maps it to customer/branch.
- No internal database/log paths are exposed in the public UI.
- Auto refresh and auto sync are always handled in background.
- UTF-8 for files/logs/API; serial protocol is ASCII-safe.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import queue
import socket
import sqlite3
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except Exception:
    requests = None

try:
    import serial
    from serial.tools import list_ports
except Exception:
    serial = None
    list_ports = None

import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from tkinter import font as tkfont

try:
    import hozoor_customer_build_config as build_config

    APP_VERSION = getattr(build_config, "APP_VERSION", "CUSTOMER-FINAL-INSTALLER-0.4.2-DEV")
    APP_NAME = getattr(build_config, "APP_NAME", "HiMate Sync")
    SERVER_URL = getattr(build_config, "SERVER_URL", "https://hozoor.example.com")
    SERVER_ID = getattr(build_config, "SERVER_ID", "HOZOOR_MAIN")
    AGENT_TOKEN = getattr(build_config, "AGENT_TOKEN", "")
    BUILD_CHANNEL = getattr(build_config, "BUILD_CHANNEL", "dev")
    DIRECTORY_API_URL = getattr(build_config, "DIRECTORY_API_URL", "https://mangroup.ir")
    DIRECTORY_API_TOKEN = getattr(build_config, "DIRECTORY_API_TOKEN", "")
except Exception:
    APP_VERSION = "CUSTOMER-FINAL-INSTALLER-0.4.2-DEV"
    APP_NAME = "HiMate Sync"
    SERVER_URL = "https://hozoor.example.com"
    SERVER_ID = "HOZOOR_MAIN"
    AGENT_TOKEN = ""
    BUILD_CHANNEL = "dev"
    DIRECTORY_API_URL = "https://mangroup.ir"
    DIRECTORY_API_TOKEN = ""


BAUDRATE = 9600

DEFAULT_SETTINGS = {
    "auto_start_sync": True,
    "read_interval_seconds": 3,
    "sync_interval_seconds": 5,
    "heartbeat_interval_seconds": 30,
    "restore_interval_seconds": 300,
    "command_interval_seconds": 10,
    "serial_timeout_seconds": 2,
    "max_batch_size": 100,
    "preferred_port": "",
    "events_endpoint": "/api/hozoor/events/batch",
    "heartbeat_endpoint": "/api/hozoor/agent/heartbeat",
    "pull_commands_endpoint": "/api/hozoor/agent/pull-commands",
    "command_result_endpoint": "/api/hozoor/agent/command-result",
    "restore_events_endpoint": "/api/hozoor/agent/restore-events",
    "restore_confirm_endpoint": "/api/hozoor/agent/restore-confirm",

    # Direct enrollment / directory API. These routes may live on a separate Laravel domain.
    "directory_users_endpoint": "/api/users",
    "directory_branches_endpoint": "/api/branches",
    "directory_devices_endpoint": "/api/devices",
    "directory_register_endpoint": "/api/fingerprints/registe",
}

# Avaye Farda-ish UI
C_BG = "#F4F5F7"
C_SURFACE = "#FFFFFF"
C_DARK = "#191C1F"
C_DARK_2 = "#22272B"
C_RED = "#B30000"
C_RED_2 = "#8F0000"
C_TEXT = "#191C1F"
C_MUTED = "#6B7280"
C_LINE = "#E5E7EB"
C_OK = "#15803D"
C_WARN = "#B45309"
C_BAD = "#B91C1C"


def app_dir() -> Path:
    root = os.getenv("APPDATA")
    if root:
        p = Path(root) / "HozoorSyncCustomer"
    else:
        p = Path.home() / ".HozoorSyncCustomer"
    p.mkdir(parents=True, exist_ok=True)
    return p


APP_DIR = app_dir()
DB_PATH = APP_DIR / "hozoor_customer.db"
LOG_PATH = APP_DIR / "hozoor_customer.log"
SETTINGS_PATH = APP_DIR / "customer_settings.json"


def local_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def utc_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        merged = dict(default)
        if isinstance(data, dict):
            merged.update(data)
        return merged
    except Exception:
        return dict(default)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def log_line(message: str) -> None:
    try:
        with LOG_PATH.open("a", encoding="utf-8", newline="\n") as f:
            f.write(f"[{local_now()}] {message}\n")
    except Exception:
        pass


def join_url(base: str, endpoint: str) -> str:
    return (base or "").strip().rstrip("/") + "/" + endpoint.lstrip("/")


def resource_path(relative: str) -> Path:
    """Find resource in PyInstaller temp, installed exe folder, or source folder."""
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(getattr(sys, "_MEIPASS")) / relative)
    try:
        candidates.append(Path(sys.executable).resolve().parent / relative)
    except Exception:
        pass
    try:
        candidates.append(Path(__file__).resolve().parent / relative)
    except Exception:
        pass

    for p in candidates:
        if p.exists():
            return p
    return candidates[0] if candidates else Path(relative)


def load_windows_font(path: Path) -> bool:
    try:
        if os.name != "nt" or not path.exists():
            return False
        FR_PRIVATE = 0x10
        added = ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0)
        return bool(added)
    except Exception:
        return False


def choose_font(root: tk.Tk) -> str:
    # Load bundled TTF if the builder/customer repo includes licensed AFY font.
    for rel in [
        "assets/fonts/AFYRegular.ttf",
        "assets/fonts/AFYBold.ttf",
        "assets/fonts/AFY Regular.ttf",
        "assets/fonts/AFY Bold.ttf",
    ]:
        load_windows_font(resource_path(rel))

    families = set(tkfont.families(root))
    for fam in [
        "AFY",
        "AFYRegular",
        "AFY Regular",
        "AFYBold",
        "AFY Bold",
        "IRANSans",
        "Vazirmatn",
        "Segoe UI",
        "Tahoma",
    ]:
        if fam in families:
            return fam
    return "Tahoma"


@dataclass
class DeviceInfo:
    port: str
    device_code: str
    title: str = ""
    last_seen: str = ""
    status: str = "online"


class HozoorDB:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.lock, self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hz_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_code TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    finger_id INTEGER NOT NULL,
                    event_time TEXT NOT NULL,
                    time_valid INTEGER DEFAULT 0,
                    raw_line TEXT NOT NULL,
                    source TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    record_hash TEXT NOT NULL,
                    previous_hash TEXT,
                    server_synced INTEGER DEFAULT 0,
                    server_synced_at TEXT,
                    pc_restored INTEGER DEFAULT 0,
                    pc_restored_at TEXT,
                    UNIQUE(device_code, event_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hz_device_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    device_code TEXT,
                    last_port TEXT,
                    last_seen_at TEXT,
                    title TEXT,
                    status TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hz_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hz_command_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command_uuid TEXT,
                    device_code TEXT,
                    command_type TEXT,
                    serial_command TEXT,
                    status TEXT,
                    response_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hz_fingerprint_registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    registration_uuid TEXT NOT NULL UNIQUE,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    username TEXT NOT NULL,
                    branch_id INTEGER,
                    device_id INTEGER NOT NULL,
                    device_code TEXT NOT NULL,
                    finger_id INTEGER NOT NULL,
                    user_name TEXT,
                    registered_at TEXT NOT NULL,
                    server_synced INTEGER DEFAULT 0,
                    server_synced_at TEXT,
                    attempts INTEGER DEFAULT 0,
                    last_error TEXT,
                    response_json TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(device_id, finger_id)
                )
            """)
            # Upgrade existing local databases created before username-only enrollment.
            columns = {row[1] for row in conn.execute("PRAGMA table_info(hz_fingerprint_registrations)").fetchall()}
            if "username" not in columns:
                conn.execute("ALTER TABLE hz_fingerprint_registrations ADD COLUMN username TEXT")
            conn.execute("UPDATE hz_fingerprint_registrations SET username=COALESCE(NULLIF(username,''), NULLIF(user_name,''), 'legacy-' || user_id)")
            conn.commit()

    def add_log(self, level: str, message: str) -> None:
        log_line(f"{level}: {message}")
        with self.lock, self.connect() as conn:
            conn.execute("INSERT INTO hz_logs(level, message, created_at) VALUES (?, ?, ?)", (level, message, local_now()))
            conn.commit()

    def update_active_device(self, info: DeviceInfo) -> None:
        with self.lock, self.connect() as conn:
            conn.execute("""
                INSERT INTO hz_device_state(id, device_code, last_port, last_seen_at, title, status)
                VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    device_code=excluded.device_code,
                    last_port=excluded.last_port,
                    last_seen_at=excluded.last_seen_at,
                    title=excluded.title,
                    status=excluded.status
            """, (info.device_code, info.port, info.last_seen, info.title, info.status))
            conn.commit()

    def active_device(self) -> Dict[str, Any]:
        with self.lock, self.connect() as conn:
            row = conn.execute("SELECT * FROM hz_device_state WHERE id=1").fetchone()
            return dict(row) if row else {}

    def compute_hash(self, event: Dict[str, Any], previous_hash: str) -> str:
        payload = "|".join([
            str(event.get("device_code", "")),
            str(event.get("event_id", "")),
            str(event.get("finger_id", "")),
            str(event.get("event_time", "")),
            str(event.get("time_valid", "")),
            str(event.get("raw_line", "")),
            str(event.get("source", "")),
            previous_hash or "",
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def insert_event(self, event: Dict[str, Any]) -> Tuple[bool, str]:
        with self.lock, self.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM hz_events WHERE device_code=? AND event_id=?",
                (event["device_code"], int(event["event_id"])),
            ).fetchone()
            if existing:
                return False, "duplicate"

            prev = conn.execute("SELECT record_hash FROM hz_events ORDER BY id DESC LIMIT 1").fetchone()
            previous_hash = prev["record_hash"] if prev else ""
            record_hash = self.compute_hash(event, previous_hash)

            conn.execute("""
                INSERT INTO hz_events(
                    device_code, event_id, finger_id, event_time, time_valid,
                    raw_line, source, received_at, record_hash, previous_hash,
                    pc_restored, pc_restored_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event["device_code"], int(event["event_id"]), int(event["finger_id"]),
                str(event["event_time"]), int(event.get("time_valid", 0)), str(event["raw_line"]),
                str(event["source"]), local_now(), record_hash, previous_hash,
                1 if event.get("source") == "server_restore" else 0,
                local_now() if event.get("source") == "server_restore" else None,
            ))
            conn.commit()
            return True, "inserted"

    def unsynced_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.lock, self.connect() as conn:
            rows = conn.execute("""
                SELECT * FROM hz_events
                WHERE server_synced=0
                ORDER BY id ASC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def mark_synced_until(self, device_code: str, event_id: int) -> None:
        with self.lock, self.connect() as conn:
            conn.execute("""
                UPDATE hz_events
                SET server_synced=1, server_synced_at=?
                WHERE device_code=? AND event_id<=?
            """, (local_now(), device_code, int(event_id)))
            conn.commit()

    def counts(self) -> Dict[str, int]:
        with self.lock, self.connect() as conn:
            total = conn.execute("SELECT COUNT(*) c FROM hz_events").fetchone()["c"]
            unsynced = conn.execute("SELECT COUNT(*) c FROM hz_events WHERE server_synced=0").fetchone()["c"]
            restored = conn.execute("SELECT COUNT(*) c FROM hz_events WHERE source='server_restore'").fetchone()["c"]
            return {"total": total, "unsynced": unsynced, "restored": restored}

    def recent_events(self, limit: int = 60) -> List[Dict[str, Any]]:
        with self.lock, self.connect() as conn:
            rows = conn.execute("""
                SELECT event_id, finger_id, event_time, source, server_synced, received_at
                FROM hz_events ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def verify_hash_chain(self) -> Tuple[bool, str]:
        with self.lock, self.connect() as conn:
            rows = conn.execute("SELECT * FROM hz_events ORDER BY id ASC").fetchall()
            previous_hash = ""
            for row in rows:
                d = dict(row)
                event = {
                    "device_code": d["device_code"],
                    "event_id": d["event_id"],
                    "finger_id": d["finger_id"],
                    "event_time": d["event_time"],
                    "time_valid": d["time_valid"],
                    "raw_line": d["raw_line"],
                    "source": d["source"],
                }
                expected = self.compute_hash(event, previous_hash)
                if d["previous_hash"] != previous_hash or d["record_hash"] != expected:
                    return False, "هشدار امنیتی: دیتابیس محلی دستکاری شده یا آسیب دیده است."
                previous_hash = d["record_hash"]
            return True, "دیتابیس محلی سالم است"

    def record_command_log(self, command_uuid: str, device_code: str, command_type: str, serial_command: str, status: str, response: Any) -> None:
        with self.lock, self.connect() as conn:
            conn.execute("""
                INSERT INTO hz_command_logs(command_uuid, device_code, command_type, serial_command, status, response_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                command_uuid, device_code, command_type, serial_command, status,
                json.dumps(response, ensure_ascii=False), local_now(),
            ))
            conn.commit()


    def save_fingerprint_registration(self, item: Dict[str, Any]) -> Tuple[bool, str]:
        """Persist a successful hardware enrollment before/while reporting it to Laravel."""
        with self.lock, self.connect() as conn:
            existing = conn.execute(
                "SELECT id, username, registration_uuid FROM hz_fingerprint_registrations WHERE device_id=? AND finger_id=?",
                (int(item["device_id"]), int(item["finger_id"])),
            ).fetchone()
            if existing:
                if str(existing["username"] or "") == str(item["username"]):
                    return True, "already_saved"
                return False, "slot_conflict"

            conn.execute("""
                INSERT INTO hz_fingerprint_registrations(
                    registration_uuid, user_id, username, branch_id, device_id, device_code,
                    finger_id, user_name, registered_at, server_synced, attempts,
                    last_error, response_json, created_at
                ) VALUES (?, 0, ?, ?, ?, ?, ?, ?, ?, 0, 0, NULL, NULL, ?)
            """, (
                str(item["registration_uuid"]), str(item["username"]),
                int(item["branch_id"]) if item.get("branch_id") not in (None, "") else None,
                int(item["device_id"]), str(item["device_code"]),
                int(item["finger_id"]), str(item.get("user_name") or item["username"]),
                str(item["registered_at"]), local_now(),
            ))
            conn.commit()
            return True, "inserted"

    def pending_fingerprint_registrations(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.lock, self.connect() as conn:
            rows = conn.execute("""
                SELECT * FROM hz_fingerprint_registrations
                WHERE server_synced=0
                ORDER BY id ASC
                LIMIT ?
            """, (int(limit),)).fetchall()
            return [dict(row) for row in rows]

    def mark_fingerprint_registration_synced(self, registration_uuid: str, response: Any) -> None:
        with self.lock, self.connect() as conn:
            conn.execute("""
                UPDATE hz_fingerprint_registrations
                SET server_synced=1, server_synced_at=?, attempts=attempts+1,
                    last_error=NULL, response_json=?
                WHERE registration_uuid=?
            """, (
                local_now(), json.dumps(response, ensure_ascii=False),
                str(registration_uuid),
            ))
            conn.commit()

    def mark_fingerprint_registration_failed(self, registration_uuid: str, error: str, response: Any = None) -> None:
        with self.lock, self.connect() as conn:
            conn.execute("""
                UPDATE hz_fingerprint_registrations
                SET attempts=attempts+1, last_error=?, response_json=?
                WHERE registration_uuid=?
            """, (
                str(error)[:1000],
                json.dumps(response, ensure_ascii=False) if response is not None else None,
                str(registration_uuid),
            ))
            conn.commit()

    def fingerprint_registration_for_slot(self, device_id: int, finger_id: int) -> Optional[Dict[str, Any]]:
        """Return the locally known mapping for one device slot, if any."""
        with self.lock, self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM hz_fingerprint_registrations WHERE device_id=? AND finger_id=? LIMIT 1",
                (int(device_id), int(finger_id)),
            ).fetchone()
            return dict(row) if row else None

    def local_used_finger_ids(self, device_id: int) -> List[int]:
        with self.lock, self.connect() as conn:
            rows = conn.execute("""
                SELECT finger_id FROM hz_fingerprint_registrations
                WHERE device_id=?
                ORDER BY finger_id ASC
            """, (int(device_id),)).fetchall()
            return [int(row["finger_id"]) for row in rows]

    def local_next_finger_id(self, device_id: int, maximum: int = 1000) -> int:
        used = set(self.local_used_finger_ids(device_id))
        for finger_id in range(1, int(maximum) + 1):
            if finger_id not in used:
                return finger_id
        raise RuntimeError("ظرفیت کدهای اثر انگشت این دستگاه پر شده است")



class SerialBridge:
    def __init__(self, db: HozoorDB):
        self.db = db
        self.serial_lock = threading.RLock()

    def available_ports(self) -> List[str]:
        if list_ports is None:
            return []
        return [p.device for p in list_ports.comports()]

    def send_command(self, port: str, command: str, timeout: int = 3) -> List[str]:
        if serial is None:
            raise RuntimeError("pyserial نصب نیست")
        lines: List[str] = []
        with self.serial_lock:
            with serial.Serial(port, BAUDRATE, timeout=0.3, write_timeout=1) as ser:
                time.sleep(0.2)
                ser.reset_input_buffer()
                ser.write((command.strip() + "\n").encode("ascii", errors="ignore"))
                ser.flush()
                end_at = time.time() + timeout
                while time.time() < end_at:
                    raw = ser.readline()
                    if not raw:
                        time.sleep(0.05)
                        continue
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line:
                        lines.append(line)
                        if command in ("R", "SEND_PENDING"):
                            if line.startswith("END,EVENTS"):
                                break
                        else:
                            if line.startswith(("OK,", "ERR,", "PONG,", "DEVICE,")):
                                break
        return lines

    def parse_device_code(self, lines: List[str]) -> str:
        for line in lines:
            if line.startswith("DEVICE,") or line.startswith("PONG,"):
                parts = line.split(",")
                if len(parts) >= 2:
                    return parts[1].strip()
            if "DEVICE=" in line:
                for part in line.split(","):
                    if part.startswith("DEVICE="):
                        return part.split("=", 1)[1].strip()
        return ""

    def detect_one_device(self) -> Optional[DeviceInfo]:
        ports = self.available_ports()
        settings = read_json(SETTINGS_PATH, DEFAULT_SETTINGS)
        preferred = str(settings.get("preferred_port", "")).strip()
        if preferred and preferred in ports:
            ports = [preferred] + [p for p in ports if p != preferred]

        for port in ports:
            try:
                lines = self.send_command(port, "DEVICE", timeout=2)
                code = self.parse_device_code(lines)
                if not code:
                    lines = self.send_command(port, "PING", timeout=2)
                    code = self.parse_device_code(lines)
                if not code:
                    continue
                info = DeviceInfo(port=port, device_code=code, title=code, last_seen=local_now(), status="online")
                self.db.update_active_device(info)
                return info
            except Exception as exc:
                log_line(f"detect {port} failed: {exc}")
        return None

    def parse_event_line(self, line: str) -> Optional[Dict[str, Any]]:
        if not line.startswith("EVT,"):
            return None
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            return None
        try:
            return {
                "device_code": parts[1],
                "event_id": int(parts[2]),
                "finger_id": int(parts[3]),
                "event_time": parts[4],
                "time_valid": int(parts[5]),
                "raw_line": line,
                "source": "serial_agent",
            }
        except Exception:
            return None

    def read_pending(self, device: DeviceInfo) -> Tuple[int, int]:
        inserted = 0
        duplicates = 0
        lines = self.send_command(device.port, "R", timeout=5)
        for line in lines:
            event = self.parse_event_line(line)
            if not event:
                continue
            ok, reason = self.db.insert_event(event)
            if ok:
                inserted += 1
            elif reason == "duplicate":
                duplicates += 1
        return inserted, duplicates

    def ack_until(self, port: str, event_id: int) -> List[str]:
        return self.send_command(port, f"ACK,{int(event_id)}", timeout=3)

    def command_for_device(self, command_type: str, payload: Dict[str, Any]) -> str:
        t = (command_type or "").strip().upper()
        payload = payload or {}

        if t == "PING":
            return "PING"
        if t == "DEVICE":
            return "DEVICE"
        if t == "STATUS":
            return "STATUS"
        if t in ("TIME", "GET_TIME"):
            return "TIME?"
        if t in ("READ_EVENTS", "SEND_PENDING"):
            return "R"

        if t in ("ENROLL_FINGER", "ENROLL", "ADD_FINGER"):
            finger_id = int(payload.get("finger_id", 0))
            if finger_id <= 0:
                raise ValueError("finger_id is required for ENROLL_FINGER")
            return f"A {finger_id}"

        if t in ("DELETE_FINGER", "DELETE", "REMOVE_FINGER"):
            finger_id = int(payload.get("finger_id", 0))
            if finger_id <= 0:
                raise ValueError("finger_id is required for DELETE_FINGER")
            return f"M {finger_id}"

        if t in ("SET_TIME", "SET_SERVER_TIME"):
            timestamp = str(payload.get("timestamp") or payload.get("server_time") or "").strip()
            if not (len(timestamp) == 14 and timestamp.isdigit()):
                raise ValueError("timestamp/server_time must be YYYYMMDDHHMMSS for SET_TIME")
            return f"TS {timestamp}"

        if t == "REBOOT":
            return "REBOOT"
        raise ValueError(f"Unsupported command_type: {command_type}")

    def timeout_for_command(self, command_type: str) -> int:
        t = (command_type or "").strip().upper()
        if t in ("ENROLL_FINGER", "ENROLL", "ADD_FINGER"):
            # Finger enrollment can take time because the user must place the finger on sensor.
            return 90
        if t in ("DELETE_FINGER", "DELETE", "REMOVE_FINGER"):
            return 20
        if t in ("SET_TIME", "SET_SERVER_TIME", "TIME", "GET_TIME"):
            return 8
        return 15


class LaravelClient:
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings

    def headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "X-Hozoor-Server-ID": SERVER_ID,
            "X-Hozoor-Agent-Version": APP_VERSION,
            "X-Hozoor-Build-Channel": BUILD_CHANNEL,
        }
        if AGENT_TOKEN:
            headers["Authorization"] = f"Bearer {AGENT_TOKEN}"
        return headers

    def post(self, endpoint_key: str, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests نصب نیست")
        endpoint = self.settings.get(endpoint_key, DEFAULT_SETTINGS[endpoint_key])
        url = join_url(SERVER_URL, endpoint)
        response = requests.post(url, headers=self.headers(), json=payload, timeout=timeout)

        try:
            data = response.json()
        except Exception:
            data = None

        if 200 <= response.status_code < 300:
            return data if isinstance(data, dict) else {}

        # Laravel validation / business errors may still return JSON. Keep them parsable.
        if isinstance(data, dict):
            data["_http_status"] = response.status_code
            return data

        # Never show raw HTML error pages in customer UI. HTTP 502/503/504 usually means
        # webserver/proxy/PHP-FPM/Laravel failure on server side, not device failure.
        text = (response.text or "").replace("\n", " ").replace("\r", " ").strip()
        if response.status_code in (502, 503, 504):
            raise RuntimeError(f"HTTP {response.status_code}: خطای وب‌سرور یا پروکسی سمت سرور مرکزی. لاگ Laravel/PHP-FPM را بررسی کنید.")
        raise RuntimeError(f"HTTP {response.status_code}: پاسخ غیر JSON از سرور ({endpoint})")

    def heartbeat(self, device: Optional[DeviceInfo], counts: Dict[str, int], hash_ok: bool, hash_msg: str) -> Dict[str, Any]:
        return self.post("heartbeat_endpoint", {
            "agent_version": APP_VERSION,
            "server_id": SERVER_ID,
            "pc_name": socket.gethostname(),
            "source": "customer_final_ui",
            "device": {
                "device_code": device.device_code,
                "port": device.port,
                "status": device.status,
                "last_seen": device.last_seen,
            } if device else None,
            "local_counts": counts,
            "hash_chain_ok": hash_ok,
            "hash_message": hash_msg,
            "time": utc_now(),
        }, timeout=30)

    def sync_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.post("events_endpoint", {
            "agent_version": APP_VERSION,
            "server_id": SERVER_ID,
            "source": "serial_agent",
            "pc_name": socket.gethostname(),
            "events": [
                {
                    "device_code": e["device_code"],
                    "event_id": int(e["event_id"]),
                    "finger_id": int(e["finger_id"]),
                    "event_time": e["event_time"],
                    "time_valid": int(e["time_valid"]),
                    "raw_line": e["raw_line"],
                    "source": e["source"],
                    "record_hash": e["record_hash"],
                } for e in events
            ],
        }, timeout=45)

    def restore_events(self, device_code: str = "") -> List[Dict[str, Any]]:
        data = self.post("restore_events_endpoint", {
            "agent_version": APP_VERSION,
            "server_id": SERVER_ID,
            "pc_name": socket.gethostname(),
            "device_code": device_code,
        }, timeout=45)
        return data.get("restore_events", []) if data.get("ok") else []

    def restore_confirm(self, restored: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.post("restore_confirm_endpoint", {
            "agent_version": APP_VERSION,
            "server_id": SERVER_ID,
            "pc_name": socket.gethostname(),
            "restored": [{"device_code": e["device_code"], "event_id": int(e["event_id"])} for e in restored],
        }, timeout=45)

    def pull_commands(self, device: Optional[DeviceInfo]) -> List[Dict[str, Any]]:
        data = self.post("pull_commands_endpoint", {
            "agent_version": APP_VERSION,
            "server_id": SERVER_ID,
            "pc_name": socket.gethostname(),
            "device": {
                "device_code": device.device_code,
                "port": device.port,
                "status": device.status,
            } if device else None,
        }, timeout=30)
        return data.get("commands", []) if data.get("ok") else []

    def command_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(result)
        payload.update({"agent_version": APP_VERSION, "server_id": SERVER_ID, "pc_name": socket.gethostname()})
        return self.post("command_result_endpoint", payload, timeout=20)



class DirectoryApiClient:
    """Client for users/branches/devices/fingerprint registration APIs."""

    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings

    def headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "X-HiMate-Agent-Version": APP_VERSION,
        }
        if DIRECTORY_API_TOKEN:
            headers["Authorization"] = f"Bearer {DIRECTORY_API_TOKEN}"
            headers["X-HiMate-Token"] = DIRECTORY_API_TOKEN
        return headers

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 25,
    ) -> Any:
        if requests is None:
            raise RuntimeError("requests نصب نیست")
        url = join_url(DIRECTORY_API_URL, endpoint)
        response = requests.request(
            method.upper(),
            url,
            headers=self.headers(),
            params=params or None,
            json=payload if payload is not None else None,
            timeout=timeout,
        )
        try:
            data = response.json()
        except Exception:
            data = None

        if 200 <= response.status_code < 300:
            return data

        if isinstance(data, dict):
            message = data.get("message") or data.get("error") or f"HTTP {response.status_code}"
            exc = RuntimeError(str(message))
            setattr(exc, "status_code", response.status_code)
            setattr(exc, "response_json", data)
            raise exc

        if response.status_code in (502, 503, 504):
            raise RuntimeError(f"HTTP {response.status_code}: سرویس فهرست کاربران/دستگاه‌ها موقتاً در دسترس نیست")
        raise RuntimeError(f"HTTP {response.status_code}: پاسخ نامعتبر از سرویس فهرست‌ها")

    @staticmethod
    def _extract_list(data: Any, keys: Tuple[str, ...]) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in keys:
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            nested = data.get("data")
            if isinstance(nested, dict):
                for key in keys:
                    value = nested.get(key)
                    if isinstance(value, list):
                        return [item for item in value if isinstance(item, dict)]
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        return []

    @staticmethod
    def _first(item: Dict[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in item and item.get(key) not in (None, ""):
                return item.get(key)
        return default

    def users(self, branch_id: Optional[int] = None) -> List[Dict[str, Any]]:
        endpoint = self.settings.get("directory_users_endpoint", DEFAULT_SETTINGS["directory_users_endpoint"])
        params = {"branch_id": int(branch_id)} if branch_id else None
        rows = self._extract_list(self._request("GET", endpoint, params=params), ("users", "employees", "items"))
        result = []
        for row in rows:
            username = self._first(row, "username", "user_name", "login", "email")
            if username in (None, ""):
                continue
            name = self._first(row, "name", "full_name", "display_name", "title", default=str(username))
            result.append({
                "username": str(username),
                "name": str(name),
                "branch_id": self._first(row, "branch_id"),
                "employee_code": self._first(row, "employee_code", "code", "personnel_code"),
                "raw": row,
            })
        return result

    def branches(self) -> List[Dict[str, Any]]:
        endpoint = self.settings.get("directory_branches_endpoint", DEFAULT_SETTINGS["directory_branches_endpoint"])
        rows = self._extract_list(self._request("GET", endpoint), ("branches", "items"))
        result = []
        for row in rows:
            branch_id = self._first(row, "id", "branch_id")
            if branch_id in (None, ""):
                continue
            title = self._first(row, "title", "name", "branch_name", default=f"شعبه {branch_id}")
            result.append({"id": int(branch_id), "title": str(title), "raw": row})
        return result

    def devices(self, branch_id: Optional[int] = None) -> List[Dict[str, Any]]:
        endpoint = self.settings.get("directory_devices_endpoint", DEFAULT_SETTINGS["directory_devices_endpoint"])
        params = {"branch_id": int(branch_id)} if branch_id else None
        rows = self._extract_list(self._request("GET", endpoint, params=params), ("devices", "items"))
        result = []
        for row in rows:
            device_id = self._first(row, "id", "device_id")
            device_code = self._first(row, "device_code", "code", "deviceCode")
            if device_id in (None, "") or device_code in (None, ""):
                continue
            title = self._first(row, "device_title", "title", "name", default=str(device_code))
            result.append({
                "id": int(device_id),
                "device_code": str(device_code).strip(),
                "title": str(title),
                "branch_id": self._first(row, "branch_id"),
                "raw": row,
            })
        return result

    def register_fingerprint(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        endpoint = self.settings.get("directory_register_endpoint", DEFAULT_SETTINGS["directory_register_endpoint"])
        exact_payload = {
            "username": str(payload["username"]),
            "device_id": int(payload["device_id"]),
            "device_code": str(payload["device_code"]),
            "finger_id": int(payload["finger_id"]),
        }
        data = self._request("POST", endpoint, payload=exact_payload, timeout=30)
        if isinstance(data, dict):
            if data.get("ok") is False or data.get("success") is False:
                raise RuntimeError(str(data.get("message") or "ثبت اثر انگشت در سرور تایید نشد"))
            return data
        return {"ok": True, "data": data}



class SyncEngine:
    def __init__(self, db: HozoorDB, ui_queue: "queue.Queue[Tuple[str, Any]]"):
        self.db = db
        self.ui_queue = ui_queue
        self.settings = read_json(SETTINGS_PATH, DEFAULT_SETTINGS)
        self.serial_bridge = SerialBridge(db)
        self.client = LaravelClient(self.settings)
        self.directory_client = DirectoryApiClient(self.settings)
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.device: Optional[DeviceInfo] = None
        self.last_sync_at = "-"
        self.last_server_status = "نامشخص"
        self.service_status = "متوقف"
        self.server_is_reachable = False
        self.first_restore_done = False

    def emit(self, event: str, data: Any = None) -> None:
        self.ui_queue.put((event, data))

    def status(self, message: str) -> None:
        self.emit("status", message)
        log_line(message)

    def reload_settings(self) -> None:
        self.settings = read_json(SETTINGS_PATH, DEFAULT_SETTINGS)
        self.client = LaravelClient(self.settings)
        self.directory_client = DirectoryApiClient(self.settings)

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()
        self.service_status = "در حال کار"
        self.status("سرویس همگام‌سازی فعال شد")

    def stop(self) -> None:
        self.stop_event.set()
        self.service_status = "متوقف"
        self.status("سرویس متوقف شد")

    def run_loop(self) -> None:
        # Fast path:
        # - Read device quickly.
        # - Send pending events quickly.
        # - Do not let restore/heartbeat/commands block first sync experience.
        last_read = 0.0
        last_sync = 0.0
        last_heartbeat = time.time() - 20
        last_restore = time.time()
        last_command = time.time()

        while not self.stop_event.is_set():
            try:
                self.reload_settings()
                now = time.time()

                if now - last_read >= int(self.settings.get("read_interval_seconds", 3)):
                    self.detect_and_read()
                    last_read = now

                if now - last_sync >= int(self.settings.get("sync_interval_seconds", 5)):
                    self.sync_to_server()
                    self.sync_pending_fingerprint_registrations()
                    last_sync = now

                # Heartbeat is secondary; shorter timeout in client.
                if now - last_heartbeat >= int(self.settings.get("heartbeat_interval_seconds", 30)):
                    self.send_heartbeat()
                    last_heartbeat = now

                # Commands only after at least one reachable server check.
                if self.server_is_reachable and now - last_command >= int(self.settings.get("command_interval_seconds", 10)):
                    self.pull_and_execute_commands()
                    last_command = now

                # Restore is heavy/rare. It should not slow normal attendance sync.
                if self.server_is_reachable and now - last_restore >= int(self.settings.get("restore_interval_seconds", 300)):
                    self.restore_from_server()
                    last_restore = now

                self.emit("refresh", None)
            except Exception as exc:
                self.db.add_log("ERROR", f"loop: {exc}")
                msg = str(exc)
                if "Read timed out" in msg or "read timeout" in msg:
                    self.last_server_status = "کند / تایم‌اوت"
                    ui_msg = "پاسخ سرور کند است؛ برنامه دوباره تلاش می‌کند."
                elif "HTTP 502" in msg or "HTTP 503" in msg or "HTTP 504" in msg:
                    self.last_server_status = "خطای سرور"
                    ui_msg = "سرور مرکزی خطای وب‌سرور برگرداند؛ لاگ Laravel/PHP-FPM باید بررسی شود."
                elif "HTTPConnectionPool" in msg or "HTTPSConnectionPool" in msg or "Max retries exceeded" in msg or "Failed to establish" in msg:
                    self.last_server_status = "قطع"
                    ui_msg = "اتصال به سرور برقرار نشد؛ اینترنت، دامنه یا SSL را بررسی کنید."
                else:
                    self.last_server_status = "خطا"
                    ui_msg = msg
                self.server_is_reachable = False
                self.emit("error", ui_msg)
            time.sleep(0.5)

    def run_once(self) -> None:
        try:
            self.reload_settings()
            self.detect_and_read()
            self.sync_to_server()
            self.restore_from_server()
            self.pull_and_execute_commands()
            self.send_heartbeat()
            self.emit("refresh", None)
        except Exception as exc:
            self.db.add_log("ERROR", f"run_once: {exc}\n{traceback.format_exc()}")
            msg = str(exc)
            if "Read timed out" in msg or "read timeout" in msg:
                self.last_server_status = "کند / تایم‌اوت"
                self.emit("error", "پاسخ سرور کند است؛ چند لحظه بعد دوباره امتحان کنید.")
            elif "HTTP 502" in msg or "HTTP 503" in msg or "HTTP 504" in msg:
                self.last_server_status = "خطای سرور"
                self.emit("error", "سرور مرکزی خطای وب‌سرور برگرداند؛ لاگ Laravel/PHP-FPM باید بررسی شود.")
            else:
                self.emit("error", msg)

    def detect_and_read(self) -> None:
        self.device = self.serial_bridge.detect_one_device()
        if not self.device:
            self.status("دستگاه متصل نیست")
            return
        inserted, duplicates = self.serial_bridge.read_pending(self.device)
        self.status(f"دستگاه {self.device.device_code}: جدید {inserted} / تکراری {duplicates}")

    def sync_to_server(self) -> None:
        events = self.db.unsynced_events(int(self.settings.get("max_batch_size", 100)))
        if not events:
            return
        data = self.client.sync_events(events)

        # HTTP 200 with ok:false means the Laravel server is reachable,
        # but business validation rejected the payload. Do not show it as
        # a connection/server error in the customer UI.
        if data.get("ok") is not True:
            self.server_is_reachable = True
            message = str(data.get("message") or "پاسخ سرور تایید نشد")
            errors = data.get("errors") or {}

            is_device_problem = (
                "device_code" in errors
                or "device_code" in message
                or "Unknown or inactive" in message
            )

            if is_device_problem:
                self.last_server_status = "وصل / دستگاه ثبت نشده"
                self.status("سرور وصل است، اما کد دستگاه در پنل ثبت یا فعال نشده است")
            else:
                self.last_server_status = "وصل / نیاز به بررسی"
                self.status(message)

            # Never ACK when Laravel rejects the event.
            return

        self.last_server_status = "وصل"
        self.server_is_reachable = True
        self.last_sync_at = local_now()

        ack_allowed = data.get("ack_allowed") is True
        ack_until = data.get("ack_until_event_id")
        if ack_allowed and ack_until is not None:
            by_device: Dict[str, int] = {}
            if isinstance(ack_until, dict):
                by_device = {str(k): int(v) for k, v in ack_until.items()}
            else:
                for e in events:
                    by_device[e["device_code"]] = max(by_device.get(e["device_code"], 0), int(ack_until))
            for device_code, eid in by_device.items():
                self.db.mark_synced_until(device_code, eid)
                if self.device and self.device.device_code == device_code:
                    self.serial_bridge.ack_until(self.device.port, eid)
                    self.status(f"ارسال تایید تا رکورد {eid}")
        else:
            self.status("سرور اجازه ACK نداد؛ رکورد روی دستگاه می‌ماند")


    def sync_pending_fingerprint_registrations(self) -> None:
        for item in self.db.pending_fingerprint_registrations(limit=10):
            payload = {
                "username": str(item["username"]),
                "device_id": int(item["device_id"]),
                "device_code": str(item["device_code"]),
                "finger_id": int(item["finger_id"]),
            }
            try:
                response = self.directory_client.register_fingerprint(payload)
                self.db.mark_fingerprint_registration_synced(item["registration_uuid"], response)
                self.status(f"ثبت اثر انگشت {item['finger_id']} در سرور تایید شد")
            except Exception as exc:
                self.db.mark_fingerprint_registration_failed(item["registration_uuid"], str(exc))


    def restore_from_server(self) -> None:
        device_code = self.device.device_code if self.device else str(self.db.active_device().get("device_code", "") or "")
        events = self.client.restore_events(device_code)
        restored: List[Dict[str, Any]] = []
        for e in events:
            event = {
                "device_code": e["device_code"],
                "event_id": int(e["event_id"]),
                "finger_id": int(e["finger_id"]),
                "event_time": str(e["event_time"]),
                "time_valid": int(e.get("time_valid", 0)),
                "raw_line": str(e.get("raw_line", "")) or f"EVT,{e['device_code']},{e['event_id']},{e['finger_id']},{e['event_time']},{e.get('time_valid', 0)}",
                "source": "server_restore",
            }
            ok, reason = self.db.insert_event(event)
            if ok or reason == "duplicate":
                restored.append(event)
        if restored:
            self.client.restore_confirm(restored)
            self.status(f"{len(restored)} رکورد از سرور بازیابی شد")

    def send_heartbeat(self) -> None:
        ok_hash, hash_msg = self.db.verify_hash_chain()
        data = self.client.heartbeat(self.device, self.db.counts(), ok_hash, hash_msg)
        if data.get("ok") is True:
            self.last_server_status = "وصل"
            self.server_is_reachable = True
        else:
            self.last_server_status = "پاسخ نامعتبر"

    def pull_and_execute_commands(self) -> None:
        if not self.device:
            return
        try:
            commands = self.client.pull_commands(self.device)
        except Exception as exc:
            self.db.add_log("ERROR", f"pull-commands failed: {exc}")
            msg = str(exc)
            if "HTTP 502" in msg or "HTTP 503" in msg or "HTTP 504" in msg:
                self.status("دریافت دستور از سرور ناموفق است: خطای وب‌سرور سمت Laravel")
            else:
                self.status(f"دریافت دستور از سرور ناموفق است: {msg}")
            return

        for cmd in commands:
            command_uuid = str(cmd.get("command_uuid", ""))
            device_code = str(cmd.get("device_code", self.device.device_code))
            command_type = str(cmd.get("command_type", ""))
            payload = cmd.get("payload") or {}
            if not isinstance(payload, dict):
                payload = {}

            employee_name = str(
                payload.get("employee_name")
                or payload.get("person_name")
                or payload.get("full_name")
                or cmd.get("employee_name")
                or ""
            ).strip()
            employee_id = payload.get("employee_id") or cmd.get("employee_id")
            finger_id = payload.get("finger_id")
            command_type_upper = command_type.strip().upper()

            result = {
                "device_code": device_code,
                "command_uuid": command_uuid,
                "command_type": command_type,
                "status": "failed",
                "serial_command": "",
                "serial_response": [],
                "error_message": None,
            }

            # Enrollment is intentionally initiated only from the Windows tab.
            # Laravel may still send other commands such as SET_TIME or DELETE_FINGER.
            if command_type_upper in ("ENROLL_FINGER", "ENROLL", "ADD_FINGER"):
                result["error_message"] = "ثبت اثر انگشت فقط از تب ثبت اثر انگشت برنامه ویندوز انجام می‌شود"
                self.emit("command_notice", result["error_message"])
                self.status(result["error_message"])
                self.db.record_command_log(
                    command_uuid, device_code, command_type,
                    result["serial_command"], result["status"], result,
                )
                try:
                    self.client.command_result(result)
                except Exception as exc:
                    self.db.add_log("ERROR", f"command-result failed: {exc}")
                continue

            try:
                if device_code and device_code != self.device.device_code:
                    raise RuntimeError("دستور برای دستگاه متصل فعلی نیست")

                serial_command = self.serial_bridge.command_for_device(command_type, payload)
                timeout = self.serial_bridge.timeout_for_command(command_type)

                if command_type_upper in ("ENROLL_FINGER", "ENROLL", "ADD_FINGER"):
                    self.emit("enroll_start", {
                        "command_uuid": command_uuid,
                        "device_code": device_code,
                        "finger_id": finger_id,
                        "employee_id": employee_id,
                        "employee_name": employee_name,
                        "timeout": timeout,
                    })
                    name_part = f" برای {employee_name}" if employee_name else ""
                    self.status(f"شروع ثبت اثر انگشت{name_part} - کد انگشت {finger_id}")
                else:
                    self.emit("command_notice", f"در حال اجرای دستور {command_type_upper} برای دستگاه {device_code}")
                    self.status(f"اجرای دستور سرور: {command_type}")

                self.db.add_log("INFO", f"command pulled: {command_uuid} {device_code} {command_type} -> {serial_command}")
                lines = self.serial_bridge.send_command(self.device.port, serial_command, timeout=timeout)
                has_error = any(str(l).startswith("ERR") for l in lines)
                has_response = bool(lines)
                success = has_response and not has_error

                result.update({
                    "status": "success" if success else "failed",
                    "serial_command": serial_command,
                    "serial_response": lines,
                    "error_message": None if success else ("No response from device" if not has_response else "Device returned error"),
                })

                if command_type_upper in ("ENROLL_FINGER", "ENROLL", "ADD_FINGER"):
                    self.emit("enroll_result", {
                        "ok": success,
                        "employee_name": employee_name,
                        "employee_id": employee_id,
                        "finger_id": finger_id,
                        "response": lines,
                        "error_message": result["error_message"],
                    })
                    self.emit("command_notice", f"نتیجه ثبت اثر انگشت: {'موفق' if success else 'ناموفق'}")
                else:
                    self.emit("command_notice", f"نتیجه دستور {command_type_upper}: {'موفق' if success else 'ناموفق'}")
                self.status(f"نتیجه دستور {command_type}: {'موفق' if success else 'ناموفق'}")
            except Exception as exc:
                result["error_message"] = str(exc)
                if command_type_upper in ("ENROLL_FINGER", "ENROLL", "ADD_FINGER"):
                    self.emit("enroll_result", {
                        "ok": False,
                        "employee_name": employee_name,
                        "employee_id": employee_id,
                        "finger_id": finger_id,
                        "response": [],
                        "error_message": str(exc),
                    })
                self.emit("command_notice", f"خطا در اجرای دستور {command_type_upper}: {exc}")
                self.status(f"خطا در اجرای دستور سرور: {exc}")

            self.db.record_command_log(command_uuid, device_code, command_type, result["serial_command"], result["status"], result)
            try:
                self.client.command_result(result)
            except Exception as exc:
                self.db.add_log("ERROR", f"command-result failed: {exc}")


class HozoorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.font_family = choose_font(self)
        self.title("HiMate Sync")
        self.geometry("1120x720")
        self.minsize(980, 640)
        self.configure(bg=C_BG)

        self.db = HozoorDB(DB_PATH)
        self.ui_queue: "queue.Queue[Tuple[str, Any]]" = queue.Queue()
        self.engine = SyncEngine(self.db, self.ui_queue)

        self.current_page = "home"
        self.page_frames: Dict[str, tk.Frame] = {}
        self.nav_buttons: Dict[str, tk.Button] = {}

        self.device_code_var = tk.StringVar(value="متصل نیست")
        self.port_var = tk.StringVar(value="-")
        self.unsynced_var = tk.StringVar(value="0")
        self.server_var = tk.StringVar(value="نامشخص")
        self.service_var = tk.StringVar(value="در حال آماده‌سازی")
        self.status_var = tk.StringVar(value="آماده")
        self.last_sync_var = tk.StringVar(value="-")
        self.health_var = tk.StringVar(value="-")
        self.command_notice_var = tk.StringVar(value="دستور فعالی دریافت نشده است")
        self.enroll_window: Optional[tk.Toplevel] = None
        self.enroll_status_var = tk.StringVar(value="")

        # Direct fingerprint enrollment UI state.
        self.directory_branches: List[Dict[str, Any]] = []
        self.directory_users: List[Dict[str, Any]] = []
        self.directory_devices: List[Dict[str, Any]] = []
        self.filtered_users: List[Dict[str, Any]] = []
        self.filtered_devices: List[Dict[str, Any]] = []
        self.fp_branch_var = tk.StringVar(value="")
        self.fp_user_var = tk.StringVar(value="")
        self.fp_device_var = tk.StringVar(value="")
        self.fp_finger_id_var = tk.StringVar(value="")
        self.fp_status_var = tk.StringVar(value="برای شروع، فهرست‌ها را دریافت کنید.")

        self.setup_base_fonts()
        self.build_ui()

        if not SETTINGS_PATH.exists():
            write_json(SETTINGS_PATH, read_json(SETTINGS_PATH, DEFAULT_SETTINGS))
        else:
            self.migrate_fast_defaults()

        if read_json(SETTINGS_PATH, DEFAULT_SETTINGS).get("auto_start_sync", True):
            self.engine.start()

        self.after(500, self.process_queue)
        self.after(1000, self.auto_refresh_ui)

    def migrate_fast_defaults(self) -> None:
        # Existing installs may have old slow defaults saved in AppData.
        # Only reduce values that are still equal to the old defaults.
        settings = read_json(SETTINGS_PATH, DEFAULT_SETTINGS)
        changed = False
        migration = {
            "read_interval_seconds": (20, 3),
            "sync_interval_seconds": (20, 5),
            "heartbeat_interval_seconds": (120, 30),
            "restore_interval_seconds": (180, 300),
            "command_interval_seconds": (15, 10),
            "serial_timeout_seconds": (3, 2),
        }
        for key, (old, new) in migration.items():
            if settings.get(key) == old:
                settings[key] = new
                changed = True
        if changed:
            write_json(SETTINGS_PATH, settings)

    def setup_base_fonts(self) -> None:
        self.f_normal = (self.font_family, 10)
        self.f_small = (self.font_family, 9)
        self.f_bold = (self.font_family, 10, "bold")
        self.f_title = (self.font_family, 17, "bold")
        self.f_big = (self.font_family, 22, "bold")
        self.option_add("*Font", self.f_normal)

    def build_ui(self) -> None:
        header = tk.Frame(self, bg=C_DARK, height=76)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(header, text="HiMate Sync", bg=C_DARK, fg="white", font=self.f_title).pack(side="right", padx=24)
        tk.Label(header, text="اتصال دستگاه HiMate به سرور مرکزی", bg=C_DARK, fg="#E5E7EB", font=self.f_normal).pack(side="left", padx=24)

        body = tk.Frame(self, bg=C_BG)
        body.pack(fill="both", expand=True)

        nav = tk.Frame(body, bg=C_SURFACE, width=170, highlightthickness=1, highlightbackground=C_LINE)
        nav.pack(side="right", fill="y", padx=(0, 0), pady=0)
        nav.pack_propagate(False)

        content = tk.Frame(body, bg=C_BG)
        content.pack(side="left", fill="both", expand=True, padx=18, pady=18)

        nav_items = [
            ("home", "خانه"),
            ("fingerprint", "ثبت اثر انگشت"),
            ("device", "دستگاه"),
            ("sync", "همگام‌سازی"),
            ("settings", "تنظیمات"),
            ("support", "پشتیبانی"),
        ]
        for key, title in nav_items:
            btn = tk.Button(
                nav, text=title, bd=0, relief="flat", anchor="e",
                bg=C_SURFACE, fg=C_TEXT, activebackground="#FFF1F1", activeforeground=C_RED,
                font=self.f_bold, padx=18, pady=14,
                command=lambda k=key: self.show_page(k),
            )
            btn.pack(fill="x", pady=(0, 1))
            self.nav_buttons[key] = btn

        for key, _title in nav_items:
            frame = tk.Frame(content, bg=C_BG)
            self.page_frames[key] = frame

        self.build_home(self.page_frames["home"])
        self.build_fingerprint(self.page_frames["fingerprint"])
        self.build_device(self.page_frames["device"])
        self.build_sync(self.page_frames["sync"])
        self.build_settings(self.page_frames["settings"])
        self.build_support(self.page_frames["support"])
        self.show_page("home")

        footer = tk.Frame(self, bg=C_BG, height=34)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer, textvariable=self.status_var, bg=C_BG, fg=C_MUTED, font=self.f_small).pack(side="right", padx=18)
        tk.Label(footer, text="HiMate • اتصال امن مرکزی", bg=C_BG, fg=C_MUTED, font=self.f_small).pack(side="left", padx=18)

    def show_page(self, key: str) -> None:
        for k, frame in self.page_frames.items():
            frame.pack_forget()
            self.nav_buttons[k].configure(bg=C_SURFACE, fg=C_TEXT)
        self.page_frames[key].pack(fill="both", expand=True)
        self.nav_buttons[key].configure(bg="#FFF1F1", fg=C_RED)
        self.current_page = key

    def section_title(self, parent: tk.Frame, title: str, subtitle: str = "") -> None:
        tk.Label(parent, text=title, bg=C_BG, fg=C_TEXT, font=self.f_title).pack(anchor="e")
        if subtitle:
            tk.Label(parent, text=subtitle, bg=C_BG, fg=C_MUTED, font=self.f_small, justify="right").pack(anchor="e", pady=(5, 14))
        else:
            tk.Frame(parent, height=12, bg=C_BG).pack()

    def card(self, parent: tk.Frame, title: str, var: tk.StringVar, accent: bool = False) -> tk.Frame:
        frame = tk.Frame(parent, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_LINE)
        tk.Label(frame, text=title, bg=C_SURFACE, fg=C_MUTED, font=self.f_small).pack(anchor="e", padx=16, pady=(14, 0))
        tk.Label(frame, textvariable=var, bg=C_SURFACE, fg=C_RED if accent else C_TEXT, font=self.f_big).pack(anchor="e", padx=16, pady=(8, 16))
        return frame

    def build_home(self, parent: tk.Frame) -> None:
        self.section_title(parent, "وضعیت کلی", "خواندن و ارسال رکوردها سریع و خودکار انجام می‌شود.")

        cards = tk.Frame(parent, bg=C_BG)
        cards.pack(fill="x")
        self.card(cards, "کد دستگاه", self.device_code_var, True).pack(side="right", fill="x", expand=True, padx=6)
        self.card(cards, "در انتظار ارسال", self.unsynced_var, True).pack(side="right", fill="x", expand=True, padx=6)
        self.card(cards, "وضعیت سرور", self.server_var).pack(side="right", fill="x", expand=True, padx=6)
        self.card(cards, "وضعیت سرویس", self.service_var).pack(side="right", fill="x", expand=True, padx=6)

        actions = tk.Frame(parent, bg=C_BG)
        actions.pack(fill="x", pady=20)
        self.primary_button(actions, "شروع سرویس", self.engine.start).pack(side="right", padx=5)
        self.secondary_button(actions, "همگام‌سازی الآن", self.run_once_async).pack(side="right", padx=5)
        self.secondary_button(actions, "توقف سرویس", self.engine.stop).pack(side="right", padx=5)

        note = tk.Frame(parent, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_LINE)
        note.pack(fill="x", pady=(4, 0))
        tk.Label(
            note,
            text="این نرم‌افزار برای اتصال دستگاه HiMate به سرور مرکزی استفاده می‌شود. ارسال رکوردها خودکار انجام می‌شود.",
            bg=C_SURFACE, fg=C_TEXT, font=self.f_normal, wraplength=760, justify="right"
        ).pack(anchor="e", padx=16, pady=16)

        command_box = tk.Frame(parent, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_LINE)
        command_box.pack(fill="x", pady=(12, 0))
        tk.Label(command_box, text="آخرین دستور سرور", bg=C_SURFACE, fg=C_MUTED, font=self.f_small).pack(anchor="e", padx=16, pady=(12, 0))
        tk.Label(command_box, textvariable=self.command_notice_var, bg=C_SURFACE, fg=C_TEXT, font=self.f_bold, wraplength=760, justify="right").pack(anchor="e", padx=16, pady=(6, 14))


    def build_fingerprint(self, parent: tk.Frame) -> None:
        self.section_title(
            parent,
            "ثبت اثر انگشت",
            "فرد و دستگاه را از فهرست سرور انتخاب کنید؛ ثبت روی سنسور مستقیم از همین کامپیوتر انجام می‌شود.",
        )

        actions = tk.Frame(parent, bg=C_BG)
        actions.pack(fill="x", pady=(0, 12))
        self.primary_button(actions, "دریافت فهرست‌ها", self.refresh_directory_data_async).pack(side="right")

        form = tk.Frame(parent, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_LINE)
        form.pack(fill="x")

        def add_row(label: str, widget: tk.Widget) -> None:
            row = tk.Frame(form, bg=C_SURFACE)
            row.pack(fill="x", padx=18, pady=9)
            tk.Label(row, text=label, bg=C_SURFACE, fg=C_TEXT, font=self.f_bold, width=18, anchor="e").pack(side="right")
            widget.pack(side="right", fill="x", expand=True, padx=(12, 0))

        self.fp_branch_combo = ttk.Combobox(form, textvariable=self.fp_branch_var, state="readonly", justify="right", width=55)
        self.fp_user_combo = ttk.Combobox(form, textvariable=self.fp_user_var, state="readonly", justify="right", width=55)
        self.fp_device_combo = ttk.Combobox(form, textvariable=self.fp_device_var, state="readonly", justify="right", width=55)
        self.fp_finger_entry = tk.Entry(form, textvariable=self.fp_finger_id_var, justify="right", font=self.f_normal, bd=1, relief="solid")

        add_row("شعبه", self.fp_branch_combo)
        add_row("فرد", self.fp_user_combo)
        add_row("دستگاه", self.fp_device_combo)
        add_row("کد اثر انگشت", self.fp_finger_entry)

        self.fp_branch_combo.bind("<<ComboboxSelected>>", lambda _e: self.apply_directory_filters())

        notice = tk.Frame(parent, bg="#FFF8E7", highlightthickness=1, highlightbackground="#F0D59A")
        notice.pack(fill="x", pady=14)
        tk.Label(
            notice,
            text=(
                "شعبه فقط برای فیلتر فهرست‌هاست. پس از فشردن «شروع ثبت»، برنامه دستور را مستقیم به دستگاه متصل می‌فرستد. "
                "فقط بعد از پاسخ موفق سنسور، دقیقاً username، device_id، device_code و finger_id در Laravel ثبت می‌شود."
            ),
            bg="#FFF8E7", fg=C_TEXT, font=self.f_normal, wraplength=820, justify="right",
        ).pack(anchor="e", padx=16, pady=13)

        bottom = tk.Frame(parent, bg=C_BG)
        bottom.pack(fill="x")
        self.primary_button(bottom, "شروع ثبت اثر انگشت", self.start_direct_enrollment).pack(side="right")
        tk.Label(bottom, textvariable=self.fp_status_var, bg=C_BG, fg=C_MUTED, font=self.f_small, justify="right").pack(side="right", padx=14)

    def refresh_directory_data_async(self) -> None:
        self.fp_status_var.set("در حال دریافت فهرست شعبه‌ها، افراد و دستگاه‌ها...")
        threading.Thread(target=self._refresh_directory_data_worker, daemon=True).start()

    def _refresh_directory_data_worker(self) -> None:
        try:
            client = DirectoryApiClient(read_json(SETTINGS_PATH, DEFAULT_SETTINGS))
            branches = client.branches()
            users = client.users()
            devices = client.devices()
            self.ui_queue.put(("directory_loaded", {
                "branches": branches,
                "users": users,
                "devices": devices,
            }))
        except Exception as exc:
            self.ui_queue.put(("fingerprint_status", {
                "ok": False,
                "message": f"دریافت فهرست‌ها ناموفق بود: {exc}",
            }))

    def apply_directory_data(self, data: Dict[str, Any]) -> None:
        self.directory_branches = list(data.get("branches") or [])
        self.directory_users = list(data.get("users") or [])
        self.directory_devices = list(data.get("devices") or [])

        branch_values = [f"{item['title']}  |  ID {item['id']}" for item in self.directory_branches]
        self.fp_branch_combo["values"] = branch_values

        active_code = str(self.device_code_var.get() or "").strip()
        active_device = next((item for item in self.directory_devices if item["device_code"] == active_code), None)
        if active_device and active_device.get("branch_id"):
            branch = next((item for item in self.directory_branches if int(item["id"]) == int(active_device["branch_id"])), None)
            if branch:
                self.fp_branch_var.set(f"{branch['title']}  |  ID {branch['id']}")
        elif len(self.directory_branches) == 1:
            item = self.directory_branches[0]
            self.fp_branch_var.set(f"{item['title']}  |  ID {item['id']}")

        self.apply_directory_filters()
        self.fp_status_var.set(
            f"{len(self.directory_users)} فرد، {len(self.directory_branches)} شعبه و {len(self.directory_devices)} دستگاه دریافت شد."
        )

    def _selected_branch(self) -> Optional[Dict[str, Any]]:
        value = self.fp_branch_var.get()
        for item in self.directory_branches:
            if value == f"{item['title']}  |  ID {item['id']}":
                return item
        return None

    def _selected_user(self) -> Optional[Dict[str, Any]]:
        value = self.fp_user_var.get()
        for item in self.filtered_users:
            code = f" • {item['employee_code']}" if item.get("employee_code") else ""
            if value == f"{item['name']}{code}  |  {item['username']}":
                return item
        return None

    def _selected_directory_device(self) -> Optional[Dict[str, Any]]:
        value = self.fp_device_var.get()
        for item in self.filtered_devices:
            if value == f"{item['title']} • {item['device_code']}  |  ID {item['id']}":
                return item
        return None

    def apply_directory_filters(self) -> None:
        branch = self._selected_branch()
        branch_id = int(branch["id"]) if branch else None

        def belongs(item: Dict[str, Any]) -> bool:
            value = item.get("branch_id")
            return branch_id is None or value in (None, "") or int(value) == branch_id

        self.filtered_users = [item for item in self.directory_users if belongs(item)]
        self.filtered_devices = [item for item in self.directory_devices if belongs(item)]

        user_values = []
        for item in self.filtered_users:
            code = f" • {item['employee_code']}" if item.get("employee_code") else ""
            user_values.append(f"{item['name']}{code}  |  {item['username']}")
        self.fp_user_combo["values"] = user_values
        if self.fp_user_var.get() not in user_values:
            self.fp_user_var.set(user_values[0] if len(user_values) == 1 else "")

        device_values = [
            f"{item['title']} • {item['device_code']}  |  ID {item['id']}"
            for item in self.filtered_devices
        ]
        self.fp_device_combo["values"] = device_values

        active_code = str(self.device_code_var.get() or "").strip()
        active = next((item for item in self.filtered_devices if item["device_code"] == active_code), None)
        if active:
            self.fp_device_var.set(f"{active['title']} • {active['device_code']}  |  ID {active['id']}")
        elif self.fp_device_var.get() not in device_values:
            self.fp_device_var.set(device_values[0] if len(device_values) == 1 else "")

    def suggest_finger_id_async(self) -> None:
        device = self._selected_directory_device()
        if not device:
            self.fp_status_var.set("ابتدا دستگاه را انتخاب کنید.")
            return
        self.fp_status_var.set("در حال پیدا کردن اولین کد آزاد...")
        threading.Thread(target=self._suggest_finger_id_worker, args=(device,), daemon=True).start()

    def _suggest_finger_id_worker(self, device: Dict[str, Any]) -> None:
        try:
            finger_id = self.db.local_next_finger_id(int(device["id"]))
            self.ui_queue.put(("finger_id_suggested", int(finger_id)))
        except Exception as exc:
            self.ui_queue.put(("fingerprint_status", {
                "ok": False,
                "message": f"پیشنهاد کد آزاد ناموفق بود: {exc}",
            }))

    def start_direct_enrollment(self) -> None:
        branch = self._selected_branch()
        user = self._selected_user()
        device = self._selected_directory_device()

        if not user:
            messagebox.showwarning("ثبت اثر انگشت", "یک فرد را انتخاب کنید.")
            return
        if not device:
            messagebox.showwarning("ثبت اثر انگشت", "یک دستگاه را انتخاب کنید.")
            return
        if not self.engine.device:
            messagebox.showwarning("ثبت اثر انگشت", "دستگاه فیزیکی به این کامپیوتر متصل نیست.")
            return
        if str(self.engine.device.device_code).strip() != str(device["device_code"]).strip():
            messagebox.showwarning(
                "ثبت اثر انگشت",
                f"دستگاه متصل {self.engine.device.device_code} است، اما {device['device_code']} انتخاب شده.",
            )
            return

        try:
            finger_id = int(self.fp_finger_id_var.get().strip())
            if finger_id <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("ثبت اثر انگشت", "کد اثر انگشت باید عددی بزرگ‌تر از صفر باشد.")
            return

        existing_slot = self.db.fingerprint_registration_for_slot(int(device["id"]), finger_id)
        if existing_slot:
            existing_username = str(existing_slot.get("username") or "")
            if existing_username == str(user["username"]):
                messagebox.showinfo(
                    "ثبت اثر انگشت",
                    "این کد اثر انگشت قبلاً برای همین username روی این دستگاه ثبت شده است.",
                )
            else:
                messagebox.showwarning(
                    "ثبت اثر انگشت",
                    f"کد اثر انگشت {finger_id} قبلاً برای username دیگری روی این دستگاه استفاده شده است.",
                )
            return

        payload = {
            "branch_id": int(branch["id"]) if branch else device.get("branch_id"),
            "username": str(user["username"]),
            "user_name": str(user["name"]),
            "device_id": int(device["id"]),
            "device_code": str(device["device_code"]),
            "finger_id": finger_id,
        }
        self.fp_status_var.set(f"در حال ثبت اثر انگشت برای {user['name']}...")
        threading.Thread(target=self._direct_enrollment_worker, args=(payload,), daemon=True).start()

    def _direct_enrollment_worker(self, payload: Dict[str, Any]) -> None:
        self.ui_queue.put(("enroll_start", {
            "employee_name": payload["user_name"],
            "employee_id": None,
            "finger_id": payload["finger_id"],
            "device_code": payload["device_code"],
            "timeout": 90,
            "source": "windows_direct",
        }))
        try:
            if not self.engine.device:
                raise RuntimeError("دستگاه متصل نیست")
            command = self.engine.serial_bridge.command_for_device("ENROLL_FINGER", {"finger_id": payload["finger_id"]})
            lines = self.engine.serial_bridge.send_command(self.engine.device.port, command, timeout=90)
            success = bool(lines) and any(line.startswith("OK,") for line in lines) and not any(line.startswith("ERR,") for line in lines)
            if not success:
                raise RuntimeError("سنسور پاسخ موفق نداد" if lines else "پاسخی از دستگاه دریافت نشد")

            item = dict(payload)
            item["registration_uuid"] = str(uuid.uuid4())
            item["registered_at"] = local_now()
            saved, reason = self.db.save_fingerprint_registration(item)
            if not saved:
                if reason == "slot_conflict":
                    raise RuntimeError("این کد اثر انگشت قبلاً برای فرد دیگری روی همین دستگاه ثبت شده است")
                raise RuntimeError("ذخیره محلی ثبت اثر انگشت ناموفق بود")

            api_payload = {
                "username": item["username"],
                "device_id": item["device_id"],
                "device_code": item["device_code"],
                "finger_id": item["finger_id"],
            }

            server_ok = False
            server_message = "در صف ارسال به سرور"
            try:
                response = self.engine.directory_client.register_fingerprint(api_payload)
                self.db.mark_fingerprint_registration_synced(item["registration_uuid"], response)
                server_ok = True
                server_message = "در سرور نیز ثبت شد"
            except Exception as exc:
                self.db.mark_fingerprint_registration_failed(item["registration_uuid"], str(exc))
                server_message = f"روی دستگاه ثبت شد؛ ارسال به سرور در صف تکرار است: {exc}"

            self.ui_queue.put(("enroll_result", {
                "ok": True,
                "employee_name": item["user_name"],
                "employee_id": None,
                "finger_id": item["finger_id"],
                "response": lines,
                "error_message": None,
            }))
            self.ui_queue.put(("fingerprint_status", {
                "ok": server_ok,
                "message": f"ثبت اثر انگشت {item['user_name']} موفق بود؛ {server_message}.",
            }))
        except Exception as exc:
            self.ui_queue.put(("enroll_result", {
                "ok": False,
                "employee_name": payload.get("user_name"),
                "employee_id": None,
                "finger_id": payload.get("finger_id"),
                "response": [],
                "error_message": str(exc),
            }))
            self.ui_queue.put(("fingerprint_status", {
                "ok": False,
                "message": f"ثبت اثر انگشت ناموفق بود: {exc}",
            }))


    def build_device(self, parent: tk.Frame) -> None:
        self.section_title(parent, "دستگاه متصل", "برنامه در هر لحظه با یک دستگاه کار می‌کند و کد دستگاه را از سخت‌افزار می‌خواند.")
        box = tk.Frame(parent, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_LINE)
        box.pack(fill="x")
        rows = [
            ("کد دستگاه", self.device_code_var),
            ("درگاه اتصال", self.port_var),
            ("آخرین ارسال موفق", self.last_sync_var),
        ]
        for label, var in rows:
            row = tk.Frame(box, bg=C_SURFACE)
            row.pack(fill="x", padx=16, pady=8)
            tk.Label(row, text=label, bg=C_SURFACE, fg=C_MUTED, font=self.f_small).pack(side="right")
            tk.Label(row, textvariable=var, bg=C_SURFACE, fg=C_TEXT, font=self.f_bold).pack(side="left")

    def build_sync(self, parent: tk.Frame) -> None:
        self.section_title(parent, "همگام‌سازی", "آخرین رکوردهای دریافت‌شده از دستگاه و وضعیت ارسال به سرور.")
        top = tk.Frame(parent, bg=C_BG)
        top.pack(fill="x", pady=(0, 10))
        self.secondary_button(top, "بررسی سلامت دیتابیس", self.verify_hash).pack(side="right")
        tk.Label(top, textvariable=self.health_var, bg=C_BG, fg=C_MUTED, font=self.f_small).pack(side="right", padx=12)

        cols = ["Event ID", "Finger", "زمان رویداد", "منبع", "ارسال", "ثبت در PC"]
        widths = [90, 80, 170, 130, 100, 180]
        table = tk.Frame(parent, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_LINE)
        table.pack(fill="both", expand=True)

        header = tk.Frame(table, bg="#F0F1F3")
        header.pack(fill="x")
        for c, w in zip(cols, widths):
            tk.Label(header, text=c, bg="#F0F1F3", fg=C_TEXT, font=self.f_bold, width=max(8, w//10), anchor="center").pack(side="right", padx=1, pady=8)

        self.events_box = tk.Frame(table, bg=C_SURFACE)
        self.events_box.pack(fill="both", expand=True)

    def build_settings(self, parent: tk.Frame) -> None:
        self.section_title(parent, "تنظیمات", "فقط تنظیمات غیرحساس قابل تغییر است.")
        info = tk.Frame(parent, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_LINE)
        info.pack(fill="x", pady=(0, 14))
        tk.Label(
            info,
            text="آدرس سرور مرکزی، توکن و تنظیمات حساس داخل فایل نصب بسته‌بندی شده‌اند و در این صفحه نمایش داده نمی‌شوند.",
            bg=C_SURFACE, fg=C_TEXT, font=self.f_normal, wraplength=760, justify="right"
        ).pack(anchor="e", padx=16, pady=14)

        self.settings_vars: Dict[str, tk.StringVar] = {}
        settings = read_json(SETTINGS_PATH, DEFAULT_SETTINGS)
        fields = [
            ("read_interval_seconds", "فاصله خواندن دستگاه / ثانیه"),
            ("sync_interval_seconds", "فاصله ارسال به سرور / ثانیه"),
            ("heartbeat_interval_seconds", "فاصله وضعیت سرور / ثانیه"),
            ("restore_interval_seconds", "فاصله بازیابی از سرور / ثانیه"),
            ("preferred_port", "Port ترجیحی اختیاری"),
        ]
        form = tk.Frame(parent, bg=C_BG)
        form.pack(anchor="e")
        for key, label in fields:
            row = tk.Frame(form, bg=C_BG)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=label, bg=C_BG, fg=C_TEXT, font=self.f_normal, width=30, anchor="e").pack(side="right")
            var = tk.StringVar(value=str(settings.get(key, DEFAULT_SETTINGS.get(key, ""))))
            self.settings_vars[key] = var
            tk.Entry(row, textvariable=var, justify="right", font=self.f_normal, width=24, bd=1, relief="solid").pack(side="right", padx=8)
        self.primary_button(parent, "ذخیره تنظیمات", self.save_settings).pack(anchor="e", pady=14)

    def build_support(self, parent: tk.Frame) -> None:
        self.section_title(parent, "پشتیبانی", "اطلاعات حساس مسیر دیتابیس و لاگ برای کاربر نمایش داده نمی‌شود.")
        box = tk.Frame(parent, bg=C_SURFACE, highlightthickness=1, highlightbackground=C_LINE)
        box.pack(fill="x")
        public_info = [
            ("نسخه نرم‌افزار", APP_VERSION),
            ("وضعیت نصب", "فعال"),
            ("مرکز اتصال", "سرور مرکزی HiMate"),
            ("فونت فعال", self.font_family),
        ]
        for label, value in public_info:
            row = tk.Frame(box, bg=C_SURFACE)
            row.pack(fill="x", padx=16, pady=7)
            tk.Label(row, text=label, bg=C_SURFACE, fg=C_MUTED, font=self.f_small).pack(side="right")
            tk.Label(row, text=value, bg=C_SURFACE, fg=C_TEXT, font=self.f_bold).pack(side="left")

        actions = tk.Frame(parent, bg=C_BG)
        actions.pack(fill="x", pady=16)
        self.secondary_button(actions, "خروجی گزارش برای پشتیبانی", self.export_log).pack(side="right", padx=5)
        self.secondary_button(actions, "درباره", self.about).pack(side="right", padx=5)

    def primary_button(self, parent: tk.Frame, text: str, command) -> tk.Button:
        return tk.Button(parent, text=text, command=command, bd=0, relief="flat", bg=C_RED, fg="white",
                         activebackground=C_RED_2, activeforeground="white", font=self.f_bold, padx=18, pady=10)

    def secondary_button(self, parent: tk.Frame, text: str, command) -> tk.Button:
        return tk.Button(parent, text=text, command=command, bd=1, relief="solid", bg=C_SURFACE, fg=C_TEXT,
                         activebackground="#FFF1F1", activeforeground=C_RED, font=self.f_normal, padx=16, pady=9)

    def process_queue(self) -> None:
        try:
            while True:
                event, data = self.ui_queue.get_nowait()
                if event == "status":
                    self.status_var.set(str(data))
                elif event == "error":
                    self.status_var.set(f"خطا: {data}")
                elif event == "command_notice":
                    self.command_notice_var.set(str(data))
                elif event == "enroll_start":
                    self.show_enrollment_window(data or {})
                elif event == "enroll_result":
                    self.finish_enrollment_window(data or {})
                elif event == "directory_loaded":
                    self.apply_directory_data(data or {})
                elif event == "finger_id_suggested":
                    self.fp_finger_id_var.set(str(data))
                    self.fp_status_var.set(f"کد آزاد پیشنهادی: {data}")
                elif event == "fingerprint_status":
                    payload = data or {}
                    self.fp_status_var.set(str(payload.get("message") or ""))
                elif event == "refresh":
                    self.refresh_ui()
        except queue.Empty:
            pass
        self.after(500, self.process_queue)

    def show_enrollment_window(self, data: Dict[str, Any]) -> None:
        try:
            if self.enroll_window and self.enroll_window.winfo_exists():
                self.enroll_window.destroy()
        except Exception:
            pass

        employee_name = str(data.get("employee_name") or "").strip()
        employee_id = data.get("employee_id")
        finger_id = data.get("finger_id") or "-"
        device_code = data.get("device_code") or self.device_code_var.get()
        timeout = data.get("timeout") or 90

        title_name = employee_name or (f"شناسه کارمند {employee_id}" if employee_id else "کاربر انتخاب‌شده در پنل")
        self.command_notice_var.set(f"ثبت اثر انگشت برای {title_name} - کد انگشت {finger_id}")
        self.enroll_status_var.set("لطفاً همین حالا انگشت را روی سنسور قرار دهید و تا پایان عملیات برندارید.")

        win = tk.Toplevel(self)
        self.enroll_window = win
        win.title("ثبت اثر انگشت HiMate")
        win.geometry("520x310")
        win.resizable(False, False)
        win.configure(bg=C_SURFACE)
        try:
            win.transient(self)
            win.attributes("-topmost", True)
        except Exception:
            pass

        tk.Label(win, text="ثبت اثر انگشت", bg=C_SURFACE, fg=C_RED, font=self.f_title).pack(anchor="e", padx=24, pady=(24, 6))
        tk.Label(win, text="عملیات ثبت اثر انگشت در حال اجراست", bg=C_SURFACE, fg=C_MUTED, font=self.f_normal).pack(anchor="e", padx=24)

        info = tk.Frame(win, bg="#F8F8F8", highlightthickness=1, highlightbackground=C_LINE)
        info.pack(fill="x", padx=24, pady=16)
        rows = [
            ("نام فرد", title_name),
            ("کد انگشت", str(finger_id)),
            ("کد دستگاه", str(device_code)),
            ("مهلت تقریبی", f"{timeout} ثانیه"),
        ]
        for label, value in rows:
            row = tk.Frame(info, bg="#F8F8F8")
            row.pack(fill="x", padx=14, pady=5)
            tk.Label(row, text=label, bg="#F8F8F8", fg=C_MUTED, font=self.f_small).pack(side="right")
            tk.Label(row, text=value, bg="#F8F8F8", fg=C_TEXT, font=self.f_bold).pack(side="left")

        tk.Label(win, textvariable=self.enroll_status_var, bg=C_SURFACE, fg=C_TEXT, font=self.f_bold, wraplength=460, justify="right").pack(anchor="e", padx=24, pady=(4, 10))
        self.secondary_button(win, "بستن پنجره", win.destroy).pack(anchor="center", pady=(0, 18))

    def finish_enrollment_window(self, data: Dict[str, Any]) -> None:
        ok = bool(data.get("ok"))
        employee_name = str(data.get("employee_name") or "").strip()
        finger_id = data.get("finger_id") or "-"
        target = employee_name or "کاربر انتخاب‌شده"
        if ok:
            msg = f"ثبت اثر انگشت برای {target} با موفقیت انجام شد. کد انگشت: {finger_id}"
            self.enroll_status_var.set(msg)
            self.command_notice_var.set(msg)
        else:
            err = data.get("error_message") or "دستگاه پاسخ موفق نداد"
            msg = f"ثبت اثر انگشت برای {target} ناموفق بود. {err}"
            self.enroll_status_var.set(msg)
            self.command_notice_var.set(msg)

        try:
            if self.enroll_window and self.enroll_window.winfo_exists():
                self.enroll_window.attributes("-topmost", True)
                self.enroll_window.after(9000, self.enroll_window.destroy)
        except Exception:
            pass

    def auto_refresh_ui(self) -> None:
        self.refresh_ui()
        self.after(2000, self.auto_refresh_ui)

    def refresh_ui(self) -> None:
        counts = self.db.counts()
        active = self.db.active_device()
        self.device_code_var.set(active.get("device_code") or "متصل نیست")
        self.port_var.set(active.get("last_port") or "-")
        self.unsynced_var.set(str(counts["unsynced"]))
        self.server_var.set(self.engine.last_server_status)
        self.service_var.set(self.engine.service_status)
        self.last_sync_var.set(self.engine.last_sync_at)
        self.refresh_events()

    def refresh_events(self) -> None:
        if not hasattr(self, "events_box"):
            return
        for child in self.events_box.winfo_children():
            child.destroy()
        for i, e in enumerate(self.db.recent_events(12)):
            bg = C_SURFACE if i % 2 == 0 else "#FAFAFA"
            row = tk.Frame(self.events_box, bg=bg)
            row.pack(fill="x")
            values = [
                str(e.get("event_id", "")),
                str(e.get("finger_id", "")),
                str(e.get("event_time", "")),
                str(e.get("source", "")),
                "ارسال شد" if e.get("server_synced") else "در انتظار",
                str(e.get("received_at", "")),
            ]
            widths = [90, 80, 170, 130, 100, 180]
            for value, w in zip(values, widths):
                tk.Label(row, text=value, bg=bg, fg=C_TEXT, font=self.f_small, width=max(8, w//10), anchor="center").pack(side="right", padx=1, pady=7)

    def run_once_async(self) -> None:
        threading.Thread(target=self.engine.run_once, daemon=True).start()

    def verify_hash(self) -> None:
        ok, msg = self.db.verify_hash_chain()
        self.health_var.set(msg)
        if ok:
            messagebox.showinfo("سلامت دیتابیس", msg)
        else:
            self.db.add_log("SECURITY", msg)
            messagebox.showwarning("هشدار امنیتی", msg)

    def save_settings(self) -> None:
        settings = read_json(SETTINGS_PATH, DEFAULT_SETTINGS)
        for key, var in self.settings_vars.items():
            value = var.get().strip()
            if key.endswith("_seconds"):
                try:
                    value = int(value)
                except ValueError:
                    messagebox.showerror("خطا", "مقادیر زمانی باید عدد باشند.")
                    return
            settings[key] = value
        write_json(SETTINGS_PATH, settings)
        self.engine.reload_settings()
        messagebox.showinfo("ذخیره شد", "تنظیمات ذخیره شد.")

    def export_log(self) -> None:
        target = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="himate_support_report.log",
        )
        if not target:
            return
        try:
            content = LOG_PATH.read_text(encoding="utf-8", errors="replace") if LOG_PATH.exists() else ""
            Path(target).write_text(content, encoding="utf-8")
            messagebox.showinfo("انجام شد", "گزارش ذخیره شد.")
        except Exception as exc:
            messagebox.showerror("خطا", str(exc))

    def about(self) -> None:
        messagebox.showinfo("HiMate", f"HiMate Sync\n{APP_VERSION}\nAvaye Farda Media")


def main() -> int:
    log_line(f"Starting {APP_VERSION}")
    app = HozoorApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
