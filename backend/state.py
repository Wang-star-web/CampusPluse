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


class SimConfigStore:
    """模拟器全局配置的内存存储（A00 阶段01增量）。

    与 StateStore 同理：进程内存即事实，重启回到默认值（无残留）。
    POST /api/sim/set 在线程池线程写入，GET /api/sim/config 被模拟器
    每 2s 并发轮询 → 同样加锁 + 深拷贝。
    """

    DEFAULTS: dict = {
        "crowd": 500,              # 默认即 500 预设（按钮中位场景）
        "entrance_available": 2,
        "main_route": "normal",
        "support": 10,
        "mode": {                  # 阶段02：各对象取证模式，默认全 ok
            "crowd": "ok",
            "entrance": "ok",
            "main_route": "ok",
            "support": "ok",
        },
    }

    def __init__(self) -> None:
        self._config = dict(self.DEFAULTS)
        self._lock = threading.Lock()

    def get(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._config)

    def set(self, config: dict) -> None:
        with self._lock:
            self._config = dict(config)


sim_config = SimConfigStore()  # 模块级单例：main.py 读写；模拟器经 HTTP 间接读取
