"""CampusPulse A00 阶段01 - support 支持人员模拟器（只发布原始业务状态，不做任何态势计算）。

配置来自后端内存（POST /api/sim/set 修改），模拟器每 2s 轮询一次。
运行：py simulators/support_sim.py（仓库根目录）
"""

from common import run_simulator


def support_data(cfg: dict) -> dict:
    return {"count": cfg["support"]}


if __name__ == "__main__":
    run_simulator("support", support_data)
