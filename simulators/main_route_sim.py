"""CampusPulse A00 阶段01 - main_route 主要路线模拟器（只发布原始业务状态，不做任何态势计算）。

配置来自后端内存（POST /api/sim/set 修改），模拟器每 2s 轮询一次。
运行：py simulators/main_route_sim.py（仓库根目录）
"""

from common import run_simulator


def route_data(cfg: dict) -> dict:
    return {"status": cfg["main_route"]}


if __name__ == "__main__":
    run_simulator("main_route", route_data)
