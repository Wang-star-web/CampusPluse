"""CampusPulse A00 阶段01 - main_route 主要路线模拟器（只发布原始业务状态，不做任何态势计算）。

运行：py simulators/main_route_sim.py（仓库根目录）
"""

from common import run_simulator


def route_data(value: str) -> dict:
    return {"status": value}


if __name__ == "__main__":
    run_simulator("main_route", "main_route", route_data)
