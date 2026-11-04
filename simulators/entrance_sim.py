"""CampusPulse A00 阶段01 - entrance 入口模拟器（只发布原始业务状态，不做任何态势计算）。

"2/2" 表示 2 个入口中 2 个可用；data 字段名 available/total 与官方指南
阶段02/03（entrance_ratio = available / total）保持一致，映射 value_json 零转换。

运行：py simulators/entrance_sim.py（仓库根目录）
"""

from common import run_simulator


def entrance_data(value: str) -> dict | None:
    """'2/2' -> {"total": 2, "available": 2}"""
    try:
        available, total = (int(x) for x in value.split("/"))
    except ValueError:
        return None
    return {"total": total, "available": available}


if __name__ == "__main__":
    run_simulator("entrance", "entrance", entrance_data)
