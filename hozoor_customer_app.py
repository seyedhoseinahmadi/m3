# -*- coding: utf-8 -*-
"""
Hozoor Sync Customer Final UI v0.2.3

Rules:
- Server-bound, not device-bound.
- device_code is read from device/serial lines.
- UTF-8 for files, logs, JSON, and API.
- Serial protocol stays ASCII-safe.
- Strict ACK: Laravel must return ok:true + ack_allowed:true + ack_until_event_id.
- Local SQLite stores event content append-first with hash chain.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import queue
import socket
import sqlite3
import threading
import time
import traceback
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
from tkinter import ttk, messagebox, filedialog
from tkinter import font as tkfont

try:
    from hozoor_customer_build_config import APP_VERSION, APP_NAME, SERVER_URL, SERVER_ID, AGENT_TOKEN, BUILD_CHANNEL
except Exception:
    APP_VERSION = "CUSTOMER-FINAL-INSTALLER-0.2.9-DEV"
    APP_NAME = "Hozoor Sync"
    SERVER_URL = "https://YOUR-HOZOOR-SERVER.example.com"
    SERVER_ID = "HOZOOR_MAIN"
    AGENT_TOKEN = ""
    BUILD_CHANNEL = "dev"

BAUDRATE = 9600

# Avaye Farda UI tokens
COLOR_BG = "#F5F6F8"
COLOR_CARD = "#FFFFFF"
COLOR_TEXT = "#191C1F"
COLOR_MUTED = "#6B7280"
COLOR_LINE = "#E5E7EB"
COLOR_RED = "#B30000"
COLOR_RED_DARK = "#850000"
COLOR_DARK = "#191C1F"

def resource_path(relative: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / relative
    return Path(__file__).resolve().parent / relative

def load_private_windows_font(font_path: Path) -> bool:
    try:
        if os.name != "nt" or not font_path.exists():
            return False
        FR_PRIVATE = 0x10
        return bool(ctypes.windll.gdi32.AddFontResourceExW(str(font_path), FR_PRIVATE, 0))
    except Exception:
        return False

def choose_ui_font(root: tk.Tk) -> str:
    # Tkinter cannot reliably use WOFF/WOFF2 directly. Use TTF if product build includes it.
    for fname in ["assets/fonts/AFYRegular.ttf", "assets/fonts/AFYBold.ttf"]:
        load_private_windows_font(resource_path(fname))
    available = set(tkfont.families(root))
    for fam in ["AFY", "AFYRegular", "AFY Regular", "AvayeFarda", "Tahoma", "Segoe UI"]:
        if fam in available:
            return fam
    return "Tahoma"

DEFAULT_SETTINGS = {
    "auto_start_sync": True,
    "read_interval_seconds": 20,
    "sync_interval_seconds": 20,
    "heartbeat_interval_seconds": 120,
    "restore_interval_seconds": 180,
    "command_interval_seconds": 15,
    "serial_timeout_seconds": 3,
    "max_batch_size": 100,
    "preferred_port": "",
    "events_endpoint": "/api/hozoor/events/batch",
    "heartbeat_endpoint": "/api/hozoor/agent/heartbeat",
    "pull_commands_endpoint": "/api/hozoor/agent/pull-commands",
    "command_result_endpoint": "/api/hozoor/agent/command-result",
    "restore_events_endpoint": "/api/hozoor/agent/restore-events",
    "restore_confirm_endpoint": "/api/hozoor/agent/restore-confirm",
}

def now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def now_utc() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def data_dir() -> Path:
    root = os.getenv("APPDATA")
    p = Path(root) / "HozoorSyncCustomer" if root else Path.home() / ".HozoorSyncCustomer"
    p.mkdir(parents=True, exist_ok=True)
    return p

APP_DIR = data_dir()
DB_PATH = APP_DIR / "hozoor_customer.db"
LOG_PATH = APP_DIR / "hozoor_customer.log"
SETTINGS_PATH = APP_DIR / "customer_settings.json"

def log_line(msg: str) -> None:
    try:
        with LOG_PATH.open("a", encoding="utf-8", newline="\n") as f:
            f.write(f"[{now_local()}] {msg}\n")
    except Exception:
        pass

def read_settings() -> Dict[str, Any]:
    if SETTINGS_PATH.exists():
        try:
            loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            data = dict(DEFAULT_SETTINGS)
            if isinstance(loaded, dict):
                data.update(loaded)
            return data
        except Exception:
            pass
    SETTINGS_PATH.write_text(json.dumps(DEFAULT_SETTINGS, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(DEFAULT_SETTINGS)

def write_settings(data: Dict[str, Any]) -> None:
    SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def api_url(endpoint: str) -> str:
    return SERVER_URL.rstrip("/") + "/" + endpoint.lstrip("/")

@dataclass
class Device:
    device_code: str
    port: str
    title: str = ""
    status: str = "online"
    last_seen: str = ""

class LocalDB:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.init()

    def conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.path), timeout=30)
        c.row_factory = sqlite3.Row
        return c

    def init(self) -> None:
        with self.lock, self.conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("""
            CREATE TABLE IF NOT EXISTS hz_events(
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
                UNIQUE(device_code,event_id)
            )""")
            c.execute("""
            CREATE TABLE IF NOT EXISTS hz_devices(
                device_code TEXT PRIMARY KEY,
                last_port TEXT,
                last_seen_at TEXT,
                title TEXT,
                status TEXT
            )""")
            c.execute("""
            CREATE TABLE IF NOT EXISTS hz_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                message TEXT,
                created_at TEXT
            )""")
            c.execute("""
            CREATE TABLE IF NOT EXISTS hz_command_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_uuid TEXT,
                device_code TEXT,
                command_type TEXT,
                serial_command TEXT,
                status TEXT,
                response_json TEXT,
                created_at TEXT
            )""")
            c.commit()

    def add_log(self, level: str, message: str) -> None:
        log_line(f"{level}: {message}")
        with self.lock, self.conn() as c:
            c.execute("INSERT INTO hz_logs(level,message,created_at) VALUES(?,?,?)", (level, message, now_local()))
            c.commit()

    def event_hash(self, e: Dict[str, Any], previous_hash: str) -> str:
        payload = "|".join([
            str(e.get("device_code","")),
            str(e.get("event_id","")),
            str(e.get("finger_id","")),
            str(e.get("event_time","")),
            str(e.get("time_valid",0)),
            str(e.get("raw_line","")),
            str(e.get("source","")),
            previous_hash or ""
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def insert_event(self, e: Dict[str, Any]) -> Tuple[bool, str]:
        with self.lock, self.conn() as c:
            old = c.execute("SELECT id FROM hz_events WHERE device_code=? AND event_id=?", (e["device_code"], int(e["event_id"]))).fetchone()
            if old:
                return False, "duplicate"
            prev = c.execute("SELECT record_hash FROM hz_events ORDER BY id DESC LIMIT 1").fetchone()
            previous_hash = prev["record_hash"] if prev else ""
            h = self.event_hash(e, previous_hash)
            c.execute("""
            INSERT INTO hz_events(device_code,event_id,finger_id,event_time,time_valid,raw_line,source,received_at,record_hash,previous_hash,pc_restored,pc_restored_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                e["device_code"], int(e["event_id"]), int(e["finger_id"]), str(e["event_time"]), int(e.get("time_valid",0)),
                str(e["raw_line"]), str(e.get("source","serial_agent")), now_local(), h, previous_hash,
                1 if e.get("source") == "server_restore" else 0,
                now_local() if e.get("source") == "server_restore" else None
            ))
            c.commit()
            return True, "inserted"

    def update_device(self, d: Device) -> None:
        with self.lock, self.conn() as c:
            c.execute("""
            INSERT INTO hz_devices(device_code,last_port,last_seen_at,title,status) VALUES(?,?,?,?,?)
            ON CONFLICT(device_code) DO UPDATE SET
              last_port=excluded.last_port,
              last_seen_at=excluded.last_seen_at,
              title=excluded.title,
              status=excluded.status
            """, (d.device_code, d.port, d.last_seen, d.title, d.status))
            c.commit()

    def unsynced(self, limit: int) -> List[Dict[str, Any]]:
        with self.lock, self.conn() as c:
            rows = c.execute("SELECT * FROM hz_events WHERE server_synced=0 ORDER BY id ASC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def mark_synced_until(self, device_code: str, event_id: int) -> None:
        with self.lock, self.conn() as c:
            c.execute("UPDATE hz_events SET server_synced=1, server_synced_at=? WHERE device_code=? AND event_id<=?", (now_local(), device_code, int(event_id)))
            c.commit()

    def counts(self) -> Dict[str, int]:
        with self.lock, self.conn() as c:
            return {
                "events": c.execute("SELECT COUNT(*) c FROM hz_events").fetchone()["c"],
                "unsynced": c.execute("SELECT COUNT(*) c FROM hz_events WHERE server_synced=0").fetchone()["c"],
                "devices": c.execute("SELECT COUNT(*) c FROM hz_devices").fetchone()["c"],
                "restored": c.execute("SELECT COUNT(*) c FROM hz_events WHERE source='server_restore'").fetchone()["c"],
            }

    def devices(self) -> List[Dict[str, Any]]:
        with self.lock, self.conn() as c:
            rows = c.execute("SELECT * FROM hz_devices ORDER BY last_seen_at DESC").fetchall()
            return [dict(r) for r in rows]

    def recent(self, limit: int=120) -> List[Dict[str, Any]]:
        with self.lock, self.conn() as c:
            rows = c.execute("""
            SELECT device_code,event_id,finger_id,event_time,source,server_synced,received_at
            FROM hz_events ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def verify_hash_chain(self) -> Tuple[bool, str]:
        with self.lock, self.conn() as c:
            rows = c.execute("SELECT * FROM hz_events ORDER BY id ASC").fetchall()
            previous = ""
            for r in rows:
                d = dict(r)
                e = {k: d[k] for k in ["device_code","event_id","finger_id","event_time","time_valid","raw_line","source"]}
                expected = self.event_hash(e, previous)
                if d["previous_hash"] != previous or d["record_hash"] != expected:
                    return False, f"Hash chain broken at row {d['id']}"
                previous = d["record_hash"]
            return True, "Hash chain OK"

    def record_command(self, result: Dict[str, Any]) -> None:
        with self.lock, self.conn() as c:
            c.execute("""
            INSERT INTO hz_command_logs(command_uuid,device_code,command_type,serial_command,status,response_json,created_at)
            VALUES(?,?,?,?,?,?,?)
            """, (
                result.get("command_uuid",""), result.get("device_code",""), result.get("command_type",""),
                result.get("serial_command",""), result.get("status",""),
                json.dumps(result, ensure_ascii=False), now_local()
            ))
            c.commit()

class SerialLayer:
    def __init__(self, db: LocalDB):
        self.db = db

    def ports(self) -> List[str]:
        if list_ports is None:
            return []
        return [p.device for p in list_ports.comports()]

    def send(self, port: str, cmd: str, timeout: int=3) -> List[str]:
        if serial is None:
            raise RuntimeError("pyserial not installed")
        out: List[str] = []
        with serial.Serial(port, BAUDRATE, timeout=0.35, write_timeout=1) as s:
            time.sleep(0.2)
            s.reset_input_buffer()
            s.write((cmd.strip() + "\n").encode("ascii", errors="ignore"))
            s.flush()
            end = time.time() + timeout
            while time.time() < end:
                raw = s.readline()
                if not raw:
                    time.sleep(0.05)
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    out.append(line)
                    if cmd in ("R", "SEND_PENDING"):
                        if line.startswith("END,EVENTS"):
                            break
                    elif line.startswith(("OK,", "ERR,")):
                        break
        return out

    def extract_device_code(self, lines: List[str]) -> str:
        for line in lines:
            if line.startswith("DEVICE,") or line.startswith("PONG,"):
                p = line.split(",")
                if len(p) > 1:
                    return p[1].strip()
            if "DEVICE=" in line:
                for part in line.split(","):
                    if part.startswith("DEVICE="):
                        return part.split("=",1)[1].strip()
        return ""

    def detect(self) -> Dict[str, Device]:
        found: Dict[str, Device] = {}
        settings = read_settings()
        ports = self.ports()
        preferred = str(settings.get("preferred_port","")).strip()
        if preferred and preferred in ports:
            ports = [preferred] + [p for p in ports if p != preferred]
        for port in ports:
            try:
                lines = self.send(port, "DEVICE", 2)
                code = self.extract_device_code(lines)
                if not code:
                    lines = self.send(port, "PING", 2)
                    code = self.extract_device_code(lines)
                if code:
                    d = Device(code, port, code, "online", now_local())
                    found[code] = d
                    self.db.update_device(d)
            except Exception as exc:
                log_line(f"detect failed on {port}: {exc}")
        return found

    def parse_event(self, line: str) -> Optional[Dict[str, Any]]:
        # EVT,HZ001,event_id,finger_id,YYYYMMDDHHMMSS,time_valid
        if not line.startswith("EVT,"):
            return None
        p = [x.strip() for x in line.split(",")]
        if len(p) < 6:
            return None
        try:
            return {
                "device_code": p[1],
                "event_id": int(p[2]),
                "finger_id": int(p[3]),
                "event_time": p[4],
                "time_valid": int(p[5]),
                "raw_line": line,
                "source": "serial_agent",
            }
        except Exception:
            return None

    def read_events(self, d: Device) -> Tuple[int, int]:
        ins = dup = 0
        lines = self.send(d.port, "R", 5)
        for line in lines:
            e = self.parse_event(line)
            if not e:
                continue
            ok, reason = self.db.insert_event(e)
            if ok:
                ins += 1
            elif reason == "duplicate":
                dup += 1
        return ins, dup

    def ack(self, port: str, event_id: int) -> List[str]:
        return self.send(port, f"ACK,{int(event_id)}", 3)

    def serial_command(self, command_type: str, payload: Dict[str, Any]) -> str:
        t = command_type.strip().upper()
        if t == "PING": return "PING"
        if t == "DEVICE": return "DEVICE"
        if t == "STATUS": return "STATUS"
        if t == "TIME": return "TIME?"
        if t == "READ_EVENTS": return "R"
        if t == "ENROLL_FINGER": return f"A {int(payload['finger_id'])}"
        if t == "DELETE_FINGER": return f"M {int(payload['finger_id'])}"
        if t == "SET_SERVER_TIME": return f"TS {payload['server_time']}"
        if t == "REBOOT": return "REBOOT"
        if t == "MANUAL": return str(payload["command"]).strip()
        raise ValueError("unsupported command_type: " + t)

class ServerClient:
    def __init__(self, settings: Dict[str, Any], db: LocalDB):
        self.settings = settings
        self.db = db

    def headers(self) -> Dict[str, str]:
        h = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "X-Hozoor-Server-ID": SERVER_ID,
            "X-Hozoor-Agent-Version": APP_VERSION,
            "X-Hozoor-Build-Channel": BUILD_CHANNEL,
        }
        if AGENT_TOKEN:
            h["Authorization"] = "Bearer " + AGENT_TOKEN
        return h

    def post(self, endpoint_key: str, payload: Dict[str, Any], timeout: int=15) -> Dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests not installed")
        endpoint = self.settings.get(endpoint_key, DEFAULT_SETTINGS[endpoint_key])
        r = requests.post(api_url(endpoint), headers=self.headers(), json=payload, timeout=timeout)
        if r.status_code < 200 or r.status_code >= 300:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def heartbeat(self, devices: Dict[str, Device]) -> Dict[str, Any]:
        ok, msg = self.db.verify_hash_chain()
        return self.post("heartbeat_endpoint", {
            "agent_version": APP_VERSION,
            "server_id": SERVER_ID,
            "pc_name": socket.gethostname(),
            "source": "customer_final_ui",
            "devices": [d.__dict__ for d in devices.values()],
            "local_counts": self.db.counts(),
            "hash_chain_ok": ok,
            "hash_message": msg,
            "time": now_utc()
        }, 12)

    def sync(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        payload = {
            "agent_version": APP_VERSION,
            "server_id": SERVER_ID,
            "pc_name": socket.gethostname(),
            "source": "serial_agent",
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
            ]
        }
        return self.post("events_endpoint", payload, 25)

    def restore_events(self, device_codes: List[str]) -> List[Dict[str, Any]]:
        data = self.post("restore_events_endpoint", {
            "agent_version": APP_VERSION,
            "server_id": SERVER_ID,
            "pc_name": socket.gethostname(),
            "device_codes": device_codes,
        }, 20)
        return data.get("restore_events", []) if data.get("ok") else []

    def restore_confirm(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.post("restore_confirm_endpoint", {
            "agent_version": APP_VERSION,
            "server_id": SERVER_ID,
            "pc_name": socket.gethostname(),
            "restored": [{"device_code": e["device_code"], "event_id": int(e["event_id"])} for e in events]
        }, 15)

    def pull_commands(self, devices: Dict[str, Device]) -> List[Dict[str, Any]]:
        data = self.post("pull_commands_endpoint", {
            "agent_version": APP_VERSION,
            "server_id": SERVER_ID,
            "pc_name": socket.gethostname(),
            "devices": [d.__dict__ for d in devices.values()]
        }, 15)
        return data.get("commands", []) if data.get("ok") else []

    def command_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        p = dict(result)
        p.update({"agent_version": APP_VERSION, "server_id": SERVER_ID, "pc_name": socket.gethostname()})
        return self.post("command_result_endpoint", p, 15)

class Engine:
    def __init__(self, db: LocalDB, uiq: queue.Queue):
        self.db = db
        self.uiq = uiq
        self.settings = read_settings()
        self.serial = SerialLayer(db)
        self.server = ServerClient(self.settings, db)
        self.devices: Dict[str, Device] = {}
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.last_sync = "-"
        self.server_status = "نامشخص"

    def emit(self, name: str, data: Any=None) -> None:
        self.uiq.put((name, data))

    def status(self, msg: str) -> None:
        log_line(msg)
        self.emit("status", msg)

    def reload(self):
        self.settings = read_settings()
        self.server = ServerClient(self.settings, self.db)

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        self.status("Sync started")

    def stop(self):
        self.stop_event.set()
        self.status("Sync stopping...")

    def loop(self):
        timers = {"read":0, "sync":0, "heartbeat":0, "restore":0, "command":0}
        while not self.stop_event.is_set():
            try:
                self.reload()
                t = time.time()
                if t - timers["read"] >= int(self.settings["read_interval_seconds"]):
                    self.detect_and_read(); timers["read"] = t
                if t - timers["sync"] >= int(self.settings["sync_interval_seconds"]):
                    self.sync_to_server(); timers["sync"] = t
                if t - timers["restore"] >= int(self.settings["restore_interval_seconds"]):
                    self.restore_from_server(); timers["restore"] = t
                if t - timers["command"] >= int(self.settings["command_interval_seconds"]):
                    self.pull_commands(); timers["command"] = t
                if t - timers["heartbeat"] >= int(self.settings["heartbeat_interval_seconds"]):
                    self.heartbeat(); timers["heartbeat"] = t
                self.emit("refresh")
            except Exception as exc:
                self.db.add_log("ERROR", f"{exc}\n{traceback.format_exc()}")
                self.server_status = "قطع"
                self.emit("error", str(exc))
            time.sleep(1)
        self.status("Sync stopped")

    def once(self):
        try:
            self.reload()
            self.detect_and_read()
            self.sync_to_server()
            self.restore_from_server()
            self.pull_commands()
            self.heartbeat()
            self.emit("refresh")
        except Exception as exc:
            self.db.add_log("ERROR", f"manual sync: {exc}")
            self.emit("error", str(exc))

    def detect_and_read(self):
        self.devices = self.serial.detect()
        if not self.devices:
            self.status("No device detected")
            return
        for d in self.devices.values():
            ins, dup = self.serial.read_events(d)
            self.status(f"{d.device_code} on {d.port}: inserted={ins}, duplicate={dup}")

    def sync_to_server(self):
        events = self.db.unsynced(int(self.settings["max_batch_size"]))
        if not events:
            return
        data = self.server.sync(events)
        if data.get("ok") is not True:
            raise RuntimeError("server ok is not true")
        self.server_status = "وصل"
        self.last_sync = now_local()

        if data.get("ack_allowed") is True and data.get("ack_until_event_id") is not None:
            ack = data.get("ack_until_event_id")
            if isinstance(ack, dict):
                ack_map = {str(k): int(v) for k, v in ack.items()}
            else:
                ack_map = {}
                for e in events:
                    ack_map[e["device_code"]] = int(ack)
            for code, eid in ack_map.items():
                self.db.mark_synced_until(code, eid)
                if code in self.devices:
                    lines = self.serial.ack(self.devices[code].port, eid)
                    self.status(f"ACK {code} until {eid}: {lines}")
        else:
            self.status("Server stored events, but ACK not allowed. Device memory is kept.")

    def known_codes(self) -> List[str]:
        s = set(self.devices.keys())
        for d in self.db.devices():
            if d.get("device_code"):
                s.add(d["device_code"])
        return sorted(s)

    def restore_from_server(self):
        events = self.server.restore_events(self.known_codes())
        restored = []
        for e in events:
            ev = {
                "device_code": e["device_code"],
                "event_id": int(e["event_id"]),
                "finger_id": int(e["finger_id"]),
                "event_time": str(e["event_time"]),
                "time_valid": int(e.get("time_valid", 0)),
                "raw_line": str(e.get("raw_line") or f"EVT,{e['device_code']},{e['event_id']},{e['finger_id']},{e['event_time']},{e.get('time_valid',0)}"),
                "source": "server_restore",
            }
            ok, reason = self.db.insert_event(ev)
            if ok or reason == "duplicate":
                restored.append(ev)
        if restored:
            self.server.restore_confirm(restored)
            self.status(f"Restored {len(restored)} event(s) from server archive")

    def heartbeat(self):
        data = self.server.heartbeat(self.devices)
        self.server_status = "وصل" if data.get("ok") else "پاسخ نامعتبر"

    def pull_commands(self):
        if not self.devices:
            return
        commands = self.server.pull_commands(self.devices)
        for cmd in commands:
            result = {
                "device_code": str(cmd.get("device_code","")),
                "command_uuid": str(cmd.get("command_uuid","")),
                "command_type": str(cmd.get("command_type","")),
                "status": "failed",
                "serial_command": "",
                "serial_response": [],
                "error_message": None,
            }
            try:
                code = result["device_code"]
                if code not in self.devices:
                    raise RuntimeError(f"device not connected: {code}")
                serial_cmd = self.serial.serial_command(result["command_type"], cmd.get("payload") or {})
                lines = self.serial.send(self.devices[code].port, serial_cmd, 10)
                result["serial_command"] = serial_cmd
                result["serial_response"] = lines
                result["status"] = "failed" if any(x.startswith("ERR") for x in lines) else "success"
            except Exception as exc:
                result["error_message"] = str(exc)
            self.db.record_command(result)
            try:
                self.server.command_result(result)
            except Exception as exc:
                self.db.add_log("ERROR", "command_result: " + str(exc))

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.font_family = choose_ui_font(self)
        self.title("حضور | Hozoor Sync")
        self.geometry("1040x680")
        self.minsize(920, 600)
        self.configure(bg=COLOR_BG)

        self.db = LocalDB(DB_PATH)
        self.uiq = queue.Queue()
        self.engine = Engine(self.db, self.uiq)

        self.status_var = tk.StringVar(value="آماده")
        self.device_state_var = tk.StringVar(value="متصل نیست")
        self.device_code_var = tk.StringVar(value="-")
        self.port_var = tk.StringVar(value="-")
        self.unsynced_var = tk.StringVar(value="0")
        self.server_var = tk.StringVar(value="نامشخص")
        self.last_sync_var = tk.StringVar(value="-")
        self.hash_var = tk.StringVar(value="-")
        self.settings_vars: Dict[str, tk.StringVar] = {}

        self.style()
        self.build()
        self.after(500, self.process_ui)
        self.after(1000, self.refresh)

        if read_settings().get("auto_start_sync", True):
            self.engine.start()

    def style(self):
        try:
            ttk.Style(self).theme_use("clam")
        except Exception:
            pass
        family = self.font_family
        self.option_add("*Font", (family, 10))
        s = ttk.Style(self)
        s.configure(".", font=(family, 10), background=COLOR_BG, foreground=COLOR_TEXT)
        s.configure("TFrame", background=COLOR_BG)
        s.configure("Top.TFrame", background=COLOR_DARK)
        s.configure("Card.TFrame", background=COLOR_CARD, relief="flat", borderwidth=0)
        s.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
        s.configure("Top.TLabel", background=COLOR_DARK, foreground="#FFFFFF")
        s.configure("Muted.TLabel", background=COLOR_BG, foreground=COLOR_MUTED)
        s.configure("Card.TLabel", background=COLOR_CARD, foreground=COLOR_TEXT)
        s.configure("CardMuted.TLabel", background=COLOR_CARD, foreground=COLOR_MUTED)
        s.configure("Title.TLabel", font=(family, 18, "bold"), background=COLOR_DARK, foreground="#FFFFFF")
        s.configure("PageTitle.TLabel", font=(family, 15, "bold"), background=COLOR_BG, foreground=COLOR_TEXT)
        s.configure("Metric.TLabel", font=(family, 20, "bold"), background=COLOR_CARD, foreground=COLOR_TEXT)
        s.configure("MetricRed.TLabel", font=(family, 20, "bold"), background=COLOR_CARD, foreground=COLOR_RED)
        s.configure("TButton", padding=(12, 9), background="#FFFFFF", foreground=COLOR_TEXT)
        s.configure("Primary.TButton", font=(family, 10, "bold"), padding=(14, 10), background=COLOR_RED, foreground="#FFFFFF")
        s.map("Primary.TButton", background=[("active", COLOR_RED_DARK)], foreground=[("active", "#FFFFFF")])
        s.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(18, 9), background="#ECEEF2", foreground=COLOR_TEXT)
        s.map("TNotebook.Tab", background=[("selected", COLOR_CARD)], foreground=[("selected", COLOR_RED)])
        s.configure("Treeview", font=(family, 9), rowheight=28, background="#FFFFFF", fieldbackground="#FFFFFF", foreground=COLOR_TEXT, borderwidth=0)
        s.configure("Treeview.Heading", font=(family, 9, "bold"), background="#F0F1F3", foreground=COLOR_TEXT)

    def build(self):
        top = ttk.Frame(self, style="Top.TFrame", padding=(18, 14))
        top.pack(fill="x")
        ttk.Label(top, text="حضور | Hozoor Sync", style="Title.TLabel").pack(side="right")
        ttk.Label(top, text="نسخه مشتری نهایی — اتصال به سرور مرکزی", style="Top.TLabel").pack(side="left")

        main = ttk.Frame(self, padding=16)
        main.pack(fill="both", expand=True)

        nb = ttk.Notebook(main)
        nb.pack(fill="both", expand=True)

        self.home = ttk.Frame(nb, padding=14)
        self.device_tab = ttk.Frame(nb, padding=14)
        self.sync_tab = ttk.Frame(nb, padding=14)
        self.settings_tab = ttk.Frame(nb, padding=14)
        self.support_tab = ttk.Frame(nb, padding=14)

        nb.add(self.home, text="خانه")
        nb.add(self.device_tab, text="دستگاه")
        nb.add(self.sync_tab, text="همگام‌سازی")
        nb.add(self.settings_tab, text="تنظیمات")
        nb.add(self.support_tab, text="پشتیبانی")

        self.build_home()
        self.build_device()
        self.build_sync()
        self.build_settings()
        self.build_support()

        bottom = ttk.Frame(self, padding=(18, 9))
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status_var, foreground=COLOR_MUTED).pack(side="right")
        ttk.Label(bottom, text=f"Server ID: {SERVER_ID}", foreground=COLOR_MUTED).pack(side="left")

    def card(self, parent, title, var, red=False):
        f = ttk.Frame(parent, style="Card.TFrame", padding=16)
        ttk.Label(f, text=title, style="CardMuted.TLabel").pack(anchor="e")
        ttk.Label(f, textvariable=var, style="MetricRed.TLabel" if red else "Metric.TLabel").pack(anchor="e", pady=(8, 0))
        return f

    def build_home(self):
        ttk.Label(self.home, text="وضعیت کلی", style="PageTitle.TLabel").pack(anchor="e", pady=(0, 12))
        cards = ttk.Frame(self.home)
        cards.pack(fill="x")
        self.card(cards, "وضعیت دستگاه", self.device_state_var, red=True).pack(side="right", fill="x", expand=True, padx=6)
        self.card(cards, "کد دستگاه", self.device_code_var).pack(side="right", fill="x", expand=True, padx=6)
        self.card(cards, "در انتظار ارسال", self.unsynced_var, red=True).pack(side="right", fill="x", expand=True, padx=6)
        self.card(cards, "وضعیت سرور", self.server_var).pack(side="right", fill="x", expand=True, padx=6)

        actions = ttk.Frame(self.home)
        actions.pack(fill="x", pady=20)
        ttk.Button(actions, text="شروع", style="Primary.TButton", command=self.engine.start).pack(side="right", padx=5)
        ttk.Button(actions, text="همگام‌سازی الآن", command=self.run_once).pack(side="right", padx=5)
        ttk.Button(actions, text="توقف", command=self.engine.stop).pack(side="right", padx=5)
        ttk.Button(actions, text="بازخوانی", command=self.refresh).pack(side="right", padx=5)

        box = ttk.Frame(self.home, style="Card.TFrame", padding=16)
        box.pack(fill="x", pady=(8, 0))
        ttk.Label(box, style="Card.TLabel", justify="right", wraplength=880,
                  text="این نرم‌افزار برای اتصال یک دستگاه حضور به سرور مرکزی استفاده می‌شود. نرم‌افزار به دستگاه خاص قفل نیست؛ کد دستگاه از خود سخت‌افزار خوانده می‌شود و سرور مرکزی تشخیص می‌دهد اطلاعات متعلق به کدام مشتری و شعبه است.").pack(anchor="e")
        ttk.Label(box, style="CardMuted.TLabel", justify="right", wraplength=880,
                  text="آدرس سرور در نسخه نهایی داخل فایل نصب بسته‌بندی می‌شود و در UI مشتری قابل تغییر نیست.").pack(anchor="e", pady=(8, 0))

    def build_device(self):
        ttk.Label(self.device_tab, text="دستگاه متصل", style="PageTitle.TLabel").pack(anchor="e", pady=(0, 12))
        box = ttk.Frame(self.device_tab, style="Card.TFrame", padding=16)
        box.pack(fill="x")
        for i, (label, var) in enumerate([
            ("وضعیت", self.device_state_var),
            ("کد دستگاه", self.device_code_var),
            ("درگاه اتصال", self.port_var),
            ("آخرین همگام‌سازی", self.last_sync_var),
        ]):
            ttk.Label(box, text=label, style="CardMuted.TLabel").grid(row=i, column=1, sticky="e", padx=8, pady=8)
            ttk.Label(box, textvariable=var, style="Card.TLabel").grid(row=i, column=0, sticky="e", padx=8, pady=8)
        ttk.Button(self.device_tab, text="جستجوی دستگاه", command=self.detect).pack(anchor="e", pady=14)

    def build_sync(self):
        ttk.Label(self.sync_tab, text="رکوردهای اخیر", style="PageTitle.TLabel").pack(anchor="e", pady=(0, 12))
        top = ttk.Frame(self.sync_tab)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="بررسی سلامت دیتابیس", command=self.verify).pack(side="right", padx=4)
        ttk.Button(top, text="بازخوانی", command=self.refresh_events).pack(side="right", padx=4)
        cols = ("event_id", "finger_id", "event_time", "source", "server_synced", "received_at")
        self.events_tree = ttk.Treeview(self.sync_tab, columns=cols, show="headings", height=14)
        for c, t, w in [
            ("event_id", "Event ID", 90), ("finger_id", "Finger", 90),
            ("event_time", "زمان رویداد", 160), ("source", "منبع", 150),
            ("server_synced", "ارسال", 90), ("received_at", "زمان ثبت PC", 180)
        ]:
            self.events_tree.heading(c, text=t)
            self.events_tree.column(c, width=w, anchor="center")
        self.events_tree.pack(fill="both", expand=True)
        ttk.Label(self.sync_tab, textvariable=self.hash_var, foreground=COLOR_MUTED).pack(anchor="e", pady=(8, 0))

    def build_settings(self):
        ttk.Label(self.settings_tab, text="تنظیمات غیرحساس", style="PageTitle.TLabel").pack(anchor="e", pady=(0, 12))
        box = ttk.Frame(self.settings_tab, style="Card.TFrame", padding=16)
        box.pack(fill="x", pady=(0, 12))
        ttk.Label(box, style="Card.TLabel", justify="right", wraplength=880,
                  text="در نسخه مشتری، لینک سرور و تنظیمات حساس داخل فایل نصب بسته‌بندی می‌شوند و اینجا قابل تغییر نیستند. این بخش فقط برای تنظیمات ساده و پشتیبانی است.").pack(anchor="e")
        settings = read_settings()
        fields = [
            ("read_interval_seconds", "فاصله خواندن دستگاه / ثانیه"),
            ("sync_interval_seconds", "فاصله ارسال به سرور / ثانیه"),
            ("heartbeat_interval_seconds", "فاصله وضعیت سرور / ثانیه"),
            ("restore_interval_seconds", "فاصله بازیابی از سرور / ثانیه"),
            ("command_interval_seconds", "فاصله دریافت دستور / ثانیه"),
            ("preferred_port", "Port ترجیحی اختیاری"),
        ]
        form = ttk.Frame(self.settings_tab)
        form.pack(fill="x")
        for i, (k, label) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=i, column=1, sticky="e", padx=8, pady=6)
            v = tk.StringVar(value=str(settings.get(k, DEFAULT_SETTINGS.get(k, ""))))
            self.settings_vars[k] = v
            ttk.Entry(form, textvariable=v, width=32, justify="right").grid(row=i, column=0, sticky="e", padx=8, pady=6)
        ttk.Button(self.settings_tab, text="ذخیره تنظیمات", style="Primary.TButton", command=self.save_settings).pack(anchor="e", pady=12)

    def build_support(self):
        ttk.Label(self.support_tab, text="پشتیبانی", style="PageTitle.TLabel").pack(anchor="e", pady=(0, 12))
        box = ttk.Frame(self.support_tab, style="Card.TFrame", padding=16)
        box.pack(fill="x")
        for line in [
            f"Version: {APP_VERSION}", f"Build Channel: {BUILD_CHANNEL}", f"Server ID: {SERVER_ID}",
            f"Data Folder: {APP_DIR}", f"Database: {DB_PATH}", f"Log File: {LOG_PATH}", f"Font: {self.font_family}"
        ]:
            ttk.Label(box, text=line, style="Card.TLabel").pack(anchor="w", pady=2)
        a = ttk.Frame(self.support_tab)
        a.pack(fill="x", pady=14)
        ttk.Button(a, text="باز کردن پوشه داده", command=self.open_folder).pack(side="right", padx=4)
        ttk.Button(a, text="خروجی لاگ", command=self.export_log).pack(side="right", padx=4)
        ttk.Button(a, text="درباره", command=self.about).pack(side="right", padx=4)

    def run_once(self):
        threading.Thread(target=self.engine.once, daemon=True).start()

    def detect(self):
        def work():
            self.engine.devices = self.engine.serial.detect()
            self.uiq.put(("refresh", None))
        threading.Thread(target=work, daemon=True).start()

    def process_ui(self):
        try:
            while True:
                name, data = self.uiq.get_nowait()
                if name == "status":
                    self.status_var.set(str(data))
                elif name == "error":
                    self.status_var.set("خطا: " + str(data))
                    self.server_var.set("خطا")
                elif name == "refresh":
                    self.refresh()
        except queue.Empty:
            pass
        self.after(500, self.process_ui)

    def current_device_row(self) -> Dict[str, Any]:
        rows = self.db.devices()
        return rows[0] if rows else {}

    def refresh(self):
        c = self.db.counts()
        d = self.current_device_row()
        connected = bool(d.get("device_code"))
        self.device_state_var.set("متصل" if connected else "متصل نیست")
        self.device_code_var.set(d.get("device_code") or "-")
        self.port_var.set(d.get("last_port") or "-")
        self.unsynced_var.set(str(c["unsynced"]))
        self.server_var.set(self.engine.server_status)
        self.last_sync_var.set(self.engine.last_sync)
        self.refresh_events()

    def refresh_events(self):
        for i in self.events_tree.get_children():
            self.events_tree.delete(i)
        for e in self.db.recent(120):
            self.events_tree.insert("", "end", values=(
                e.get("event_id", ""), e.get("finger_id", ""), e.get("event_time", ""),
                e.get("source", ""), "ارسال شد" if e.get("server_synced") else "در انتظار", e.get("received_at", "")
            ))

    def save_settings(self):
        s = read_settings()
        for k, v in self.settings_vars.items():
            val = v.get().strip()
            if k.endswith("_seconds"):
                try:
                    val = int(val)
                except ValueError:
                    messagebox.showerror("خطا", f"{k} باید عدد باشد.")
                    return
            s[k] = val
        write_settings(s)
        self.engine.reload()
        messagebox.showinfo("ذخیره شد", "تنظیمات ذخیره شد.")

    def verify(self):
        ok, msg = self.db.verify_hash_chain()
        self.hash_var.set(msg)
        if ok:
            messagebox.showinfo("Database OK", msg)
        else:
            self.db.add_log("SECURITY", msg)
            messagebox.showwarning("Security Warning", msg)

    def open_folder(self):
        try:
            os.startfile(str(APP_DIR))
        except Exception:
            messagebox.showinfo("Data Folder", str(APP_DIR))

    def export_log(self):
        target = filedialog.asksaveasfilename(defaultextension=".log", initialfile="hozoor_customer.log")
        if not target:
            return
        text = LOG_PATH.read_text(encoding="utf-8", errors="replace") if LOG_PATH.exists() else ""
        Path(target).write_text(text, encoding="utf-8")
        messagebox.showinfo("Done", "Log exported.")

    def about(self):
        messagebox.showinfo("Hozoor Sync", f"حضور | Hozoor Sync\n{APP_VERSION}\n\nاتصال یک دستگاه به سرور مرکزی حضور\nAvaye Farda Media")

def main() -> int:
    log_line("Starting " + APP_VERSION)
    app = App()
    app.mainloop()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
