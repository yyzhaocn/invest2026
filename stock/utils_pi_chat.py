"""Local Pi coding agent RPC client for web chat."""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
from typing import Any, Dict, Optional

_STOCK_DIR = os.path.dirname(os.path.abspath(__file__))
_PI_BIN = shutil.which('pi') or 'pi'
_PI_TOOLS = 'read,bash,grep,find,ls'
_PI_CONFIG_VERSION = 2
_SYSTEM_PROMPT = (
    '你是股票「动态选股」页面的分析助手，专注 A 股自选股、板块与行情解读。'
    '可使用 read/bash 等工具查阅项目数据与运行分析命令。回答简洁、可执行，默认使用简体中文。'
)

_clients: Dict[str, 'PiRpcClient'] = {}
_clients_lock = threading.Lock()
_SESSION_KEY_RE = re.compile(r'^[a-zA-Z0-9_-]{8,64}$')


class PiChatError(Exception):
    pass


class PiRpcClient:
    config_version = _PI_CONFIG_VERSION

    def __init__(self, session_key: str, cwd: Optional[str] = None):
        self.session_key = session_key
        self.cwd = cwd or _STOCK_DIR
        self.proc: Optional[subprocess.Popen] = None
        self._queue: queue.Queue = queue.Queue()
        self._lock = threading.RLock()
        self._alive = False
        self._reader: Optional[threading.Thread] = None
        self.last_used = time.time()

    def is_alive(self) -> bool:
        return bool(self._alive and self.proc and self.proc.poll() is None)

    def start(self) -> None:
        with self._lock:
            if self.is_alive():
                return
            session_id = f'stock-fav-{self.session_key}'[:80]
            cmd = [
                _PI_BIN,
                '--mode', 'rpc',
                '--session-id', session_id,
                '--name', f'动态选股:{self.session_key[:8]}',
                '--tools', _PI_TOOLS,
                '-a',
                '--append-system-prompt', _SYSTEM_PROMPT,
            ]
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.cwd,
                bufsize=1,
            )
            self._alive = True
            self._reader = threading.Thread(target=self._reader_loop, daemon=True)
            self._reader.start()
            self._drain_startup_events()
            self.last_used = time.time()

    def close(self) -> None:
        with self._lock:
            self._alive = False
            proc = self.proc
            self.proc = None
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

    def reset_session(self) -> None:
        with self._lock:
            self._ensure_running()
            self._command({'type': 'new_session'}, expect_command='new_session', timeout=15)
            self.last_used = time.time()

    def send_message(self, message: str, timeout: int = 180) -> str:
        message = (message or '').strip()
        if not message:
            raise PiChatError('消息不能为空')

        with self._lock:
            self._ensure_running()
            req_id = str(uuid.uuid4())
            self._write({'id': req_id, 'type': 'prompt', 'message': message})

            accepted = False
            parts: list[str] = []
            deadline = time.time() + timeout

            while time.time() < deadline:
                ev = self._get_event(timeout=min(2.0, max(0.2, deadline - time.time())))
                if ev is None:
                    if not self.is_alive():
                        raise PiChatError('Pi 进程已退出')
                    continue

                etype = ev.get('type')
                if etype == 'response' and ev.get('id') == req_id:
                    if not ev.get('success'):
                        err = ev.get('error') or ev.get('message') or 'Pi 拒绝了请求'
                        raise PiChatError(str(err))
                    accepted = True
                    continue

                if not accepted:
                    continue

                if etype == 'message_update':
                    ame = ev.get('assistantMessageEvent') or {}
                    if ame.get('type') == 'text_delta':
                        parts.append(str(ame.get('delta') or ''))
                elif etype == 'agent_end':
                    text = ''.join(parts).strip()
                    if not text:
                        text = self._last_assistant_text()
                    self.last_used = time.time()
                    return text or '（Pi 未返回文本）'
                elif etype == 'error':
                    raise PiChatError(str(ev.get('message') or ev))

            raise PiChatError('Pi 响应超时')

    def _last_assistant_text(self) -> str:
        data = self._command({'type': 'get_last_assistant_text'}, expect_command='get_last_assistant_text', timeout=10)
        return str((data or {}).get('text') or '').strip()

    def _ensure_running(self) -> None:
        if not self.is_alive():
            self.close()
            self.start()

    def _reader_loop(self) -> None:
        assert self.proc and self.proc.stdout
        while self._alive and self.proc.poll() is None:
            line = self.proc.stdout.readline()
            if not line:
                break
            line = line.rstrip('\n').rstrip('\r')
            if not line:
                continue
            try:
                self._queue.put(json.loads(line))
            except json.JSONDecodeError:
                continue
        self._alive = False

    def _drain_startup_events(self) -> None:
        deadline = time.time() + 4
        while time.time() < deadline:
            ev = self._get_event(timeout=0.15)
            if ev is None:
                break
            if ev.get('type') == 'extension_ui_request':
                continue
            if ev.get('type') in ('response', 'error'):
                self._queue.put(ev)

    def _write(self, payload: Dict[str, Any]) -> None:
        if not self.proc or not self.proc.stdin:
            raise PiChatError('Pi 未启动')
        self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + '\n')
        self.proc.stdin.flush()

    def _get_event(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _command(self, payload: Dict[str, Any], expect_command: str, timeout: float = 30) -> Any:
        req_id = str(uuid.uuid4())
        payload = dict(payload)
        payload['id'] = req_id
        self._write(payload)
        deadline = time.time() + timeout
        while time.time() < deadline:
            ev = self._get_event(timeout=min(1.0, max(0.1, deadline - time.time())))
            if ev is None:
                continue
            if ev.get('type') == 'response' and ev.get('id') == req_id:
                if not ev.get('success'):
                    raise PiChatError(str(ev.get('error') or f'{expect_command} 失败'))
                return ev.get('data')
        raise PiChatError(f'{expect_command} 超时')


def _validate_session_key(session_key: str) -> str:
    key = (session_key or '').strip()
    if not _SESSION_KEY_RE.fullmatch(key):
        raise PiChatError('无效的 session_id')
    return key


def get_pi_client(session_key: str) -> PiRpcClient:
    key = _validate_session_key(session_key)
    with _clients_lock:
        client = _clients.get(key)
        if (
            client is None
            or not client.is_alive()
            or getattr(client, 'config_version', 0) != _PI_CONFIG_VERSION
        ):
            if client:
                client.close()
            client = PiRpcClient(key)
            client.start()
            _clients[key] = client
        client.last_used = time.time()
        return client


def pi_chat_status() -> Dict[str, Any]:
    return {
        'available': bool(_PI_BIN),
        'pi_bin': _PI_BIN,
    }


def pi_chat_send(session_key: str, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    client = get_pi_client(session_key)
    text = (message or '').strip()
    if context:
        group = str(context.get('group_name') or '').strip()
        stocks = context.get('stocks') or []
        if group or stocks:
            lines = ['[页面上下文]']
            if group:
                lines.append(f'当前分组：{group}')
            if stocks:
                preview = '；'.join(str(s) for s in stocks[:20])
                if len(stocks) > 20:
                    preview += f' …共{len(stocks)}只'
                lines.append(f'自选股：{preview}')
            text = '\n'.join(lines) + '\n\n' + text
    reply = client.send_message(text)
    return {'reply': reply}


def pi_chat_reset(session_key: str) -> None:
    client = get_pi_client(session_key)
    client.reset_session()
