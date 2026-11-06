"""CampusPulse A00 阶段01 - crowd 人数模拟器（只发布原始业务状态，不做任何态势计算）。

配置来自后端内存（POST /api/sim/set 修改），模拟器每 2s 轮询一次。
运行：py simulators/crowd_sim.py（仓库根目录）
"""

from common import run_simulator


def crowd_data(cfg: dict) -> dict:
    return {"count": cfg["crowd"]}


if __name__ == "__main__":
    run_simulator("crowd", crowd_data)
