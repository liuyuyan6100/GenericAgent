import glob
import os
import re
import threading
import time

from agentmain import GeneraticAgent
from frontends.continue_cmd import format_list, restore as restore_session_file, _pairs, _preview_text


class FeishuSessionRuntime:
    def __init__(self, project_root, open_id):
        self.project_root = project_root
        self.open_id = open_id
        self.safe_open_id = re.sub(r"[^A-Za-z0-9._-]", "_", open_id or "unknown")
        self.base_dir = os.path.join(project_root, "temp", "feishu_sessions", self.safe_open_id)
        self.log_dir = os.path.join(self.base_dir, "model_responses")
        os.makedirs(self.log_dir, exist_ok=True)
        self.agent = GeneraticAgent()
        self.agent.log_path = self.current_log_path
        threading.Thread(target=self.agent.run, daemon=True).start()

    @property
    def current_log_path(self):
        return os.path.join(self.log_dir, "model_responses_current.txt")

    def _snapshot_path(self):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        return os.path.join(
            self.log_dir,
            f"model_responses_snapshot_{stamp}_{time.time_ns() % 1_000_000_000:09d}.txt",
        )

    def _list_paths(self, include_current=False):
        files = []
        current = self.current_log_path
        if include_current and os.path.isfile(current):
            files.append(current)
        for path in glob.glob(os.path.join(self.log_dir, "model_responses_*.txt")):
            if path == current:
                continue
            files.append(path)
        return sorted(set(files), key=os.path.getmtime, reverse=True)

    def list_sessions(self):
        out = []
        for path in self._list_paths(include_current=False):
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except Exception:
                continue
            pairs = _pairs(content)
            if not pairs:
                continue
            out.append((path, os.path.getmtime(path), _preview_text(pairs), len(pairs)))
        return out

    def snapshot_current_log(self):
        path = self.current_log_path
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except Exception:
            return None
        if not _pairs(content):
            return None
        snap = self._snapshot_path()
        with open(snap, "w", encoding="utf-8", errors="replace") as fh:
            fh.write(content)
        with open(path, "w", encoding="utf-8", errors="replace"):
            pass
        return snap

    def _agent_clients(self):
        clients = list(getattr(self.agent, "llmclients", []) or [])
        current = getattr(self.agent, "llmclient", None)
        if current is not None and current not in clients:
            clients.insert(0, current)
        return clients

    def reset_conversation(self, message="🆕 已开启新对话，当前上下文已清空"):
        try:
            self.agent.abort()
        except Exception:
            pass
        self.snapshot_current_log()
        if hasattr(self.agent, "history"):
            self.agent.history = []
        for client in self._agent_clients():
            backend = getattr(client, "backend", None)
            if backend is not None and hasattr(backend, "history"):
                backend.history = []
            if hasattr(client, "last_tools"):
                client.last_tools = ""
        if hasattr(self.agent, "handler"):
            self.agent.handler = None
        self.agent.log_path = self.current_log_path
        return message

    def restore_latest(self):
        sessions = self.list_sessions()
        if not sessions:
            return "❌ 没有找到历史记录"
        self.reset_conversation(message=None)
        msg, _ = restore_session_file(self.agent, sessions[0][0])
        return msg

    def handle_continue(self, cmd):
        s = (cmd or "").strip()
        if s == "/continue":
            return format_list(self.list_sessions())
        m = re.match(r"/continue\s+(\d+)\s*$", s)
        if not m:
            return "用法: /continue 或 /continue N"
        sessions = self.list_sessions()
        idx = int(m.group(1)) - 1
        if not (0 <= idx < len(sessions)):
            return f"❌ 索引越界（有效范围 1-{len(sessions)}）"
        self.reset_conversation(message=None)
        msg, _ = restore_session_file(self.agent, sessions[idx][0])
        return msg


class FeishuSessionManager:
    def __init__(self, project_root):
        self.project_root = project_root
        self._lock = threading.Lock()
        self._runtimes = {}

    def get(self, open_id):
        with self._lock:
            runtime = self._runtimes.get(open_id)
            if runtime is None:
                runtime = FeishuSessionRuntime(self.project_root, open_id)
                self._runtimes[open_id] = runtime
            return runtime
