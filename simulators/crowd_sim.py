"""CampusPulse A00 阶段01 - crowd 人数模拟器（只发布原始业务状态，不做任何态势计算）。

运行：py simulators/crowd_sim.py（仓库根目录）
"""

from common import run_simulator


def crowd_data(value: int) -> dict:
    return {"count": value}


if __name__ == "__main__":
    run_simulator("crowd", "crowd", crowd_data)
