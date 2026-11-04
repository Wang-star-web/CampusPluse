"""对象最新状态的内存存储（A00 阶段01）。

本阶段刻意不落库（SQLite 是阶段02+ 的事）：进程内存即事实，
重启后状态从 MQTT 实时消息重新建立，不依赖任何残留。
"""

import copy
import threading
from typing import Callable

Listener = Callable[[str, dict], None]


class StateStore:
    def __init__(self) -> None:
        self._objects: dict[str, dict] = {}   # object_type -> 信封 dict（observed_at 已字符串化）
        self._lock = threading.Lock()
        self._listeners: list[Listener] = []

    def update(self, object_type: str, envelope: dict) -> None:
        with self._lock:
            self._objects[object_type] = envelope
            listeners = list(self._listeners)  # 锁内只取副本
        for fn in listeners:                   # 锁外回调，防重入死锁
            fn(object_type, envelope)

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._objects)

    def add_listener(self, fn: Listener) -> None:
        with self._lock:
            self._listeners.append(fn)

    def remove_listener(self, fn: Listener) -> None:
        with self._lock:
            if fn in self._listeners:
                self._listeners.remove(fn)


store = StateStore()  # 模块级单例：mqtt_bridge 写入，main.py 读取
