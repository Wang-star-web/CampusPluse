"""CampusPulse A00 阶段01 - support 支持人员模拟器（只发布原始业务状态，不做任何态势计算）。

运行：py simulators/support_sim.py（仓库根目录）
"""

from common import run_simulator


def support_data(value: int) -> dict:
    return {"count": value}


if __name__ == "__main__":
    run_simulator("support", "support", support_data)
