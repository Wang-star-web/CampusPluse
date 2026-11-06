"""从仓库根 .env 读取环境变量（无第三方依赖；不覆盖已有环境变量）。

uvicorn 默认不加载 .env 文件，因此在读取配置的模块顶部调用 load_dotenv()，
保证无论后端怎么启动都能读到 .env（模板见 .env.example）。
"""

import os
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_dotenv() -> None:
    if not _ENV_PATH.exists():
        return
    # 容错：.env 可能被 Windows 工具（PowerShell Set-Content / sed）写成 GBK——
    # 先按 UTF-8 读，失败按 GBK 解码
    raw = _ENV_PATH.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="ignore")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())
