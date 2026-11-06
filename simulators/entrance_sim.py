"""CampusPulse A00 阶段01 - entrance 入口模拟器（只发布原始业务状态，不做任何态势计算）。

data 字段名 available/total 与官方指南阶段02/03（entrance_ratio = available / total）
保持一致，映射 value_json 零转换；total 恒为 2，可用数来自配置 entrance_available。

配置来自后端内存（POST /api/sim/set 修改），模拟器每 2s 轮询一次。
运行：py simulators/entrance_sim.py（仓库根目录）
"""

from common import run_simulator


def entrance_data(cfg: dict) -> dict:
    return {"total": 2, "available": cfg["entrance_available"]}


if __name__ == "__main__":
    run_simulator("entrance", entrance_data)
