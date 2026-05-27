#!/usr/bin/env python3
"""
进度看板.py — 80 集长剧进度仪表盘

用法:
    cd 项目根目录
    python3 /path/to/进度看板.py

功能:
    - 总进度可视化(进度条)
    - 当前篇章 / 本周 / 本月进度
    - 工时统计 + 节奏判断
    - 资产状态
    - TODO 优先级
    - 下一步行动
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta


def load_state():
    state_path = Path("项目状态.json")
    if not state_path.exists():
        print("❌ 找不到 项目状态.json,请在项目根目录运行")
        sys.exit(1)
    with open(state_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def make_progress_bar(percent, width=40):
    filled = int(width * percent / 100)
    empty = width - filled
    return f"{'█' * filled}{'░' * empty} {percent:.1f}%"


def get_chapter_info(current_episode, total_eps=80):
    if current_episode == 0:
        return "未开工", 0, 0
    if current_episode <= 20:
        return "篇章 1(1-20 集)", current_episode, 20
    elif current_episode <= 40:
        return "篇章 2(21-40 集)", current_episode - 20, 20
    elif current_episode <= 60:
        return "篇章 3(41-60 集)", current_episode - 40, 20
    else:
        return "终章(61-80 集)", current_episode - 60, 20


def main():
    state = load_state()

    元数据 = state.get("项目元数据", {})
    项目代号 = 元数据.get("项目代号", "未知")
    片名 = 元数据.get("片名", "未填")
    立项日期 = 元数据.get("立项日期", "未填")
    预计完工 = 元数据.get("预计完工", "未填")
    总集数 = 元数据.get("总集数", 80)
    圣经版本 = 元数据.get("圣经版本", "v0")

    概览 = state.get("进度概览", {})
    已完成 = 概览.get("已完成集数", 0)
    进行中 = 概览.get("进行中集数", 0)
    完成度 = 概览.get("完成度百分比", 0.0)
    已完成镜头 = 概览.get("总镜头数_已完成", 0)
    目标镜头 = 概览.get("总镜头数_目标", 1280)

    工时 = state.get("工时记录", {})
    本月预算 = 工时.get("本月_预算小时", 0)
    本月已用 = 工时.get("本月_已用小时", 0)
    本月完成集 = 工时.get("本月_完成集数", 0)

    资产 = state.get("资产清单", {})
    角色基因数 = len(资产.get("角色基因", {}))
    服装模块数 = len(资产.get("服装模块", {}))
    场景模块数 = len(资产.get("场景模块", {}))
    法器模块数 = len(资产.get("法器模块", {}))

    todos = state.get("TODO列表", [])
    高优 = [t for t in todos if t.get("优先级") == "高"]
    中优 = [t for t in todos if t.get("优先级") == "中"]
    低优 = [t for t in todos if t.get("优先级") == "低"]

    审查记录 = state.get("跨集审查记录", [])
    最近审查 = 审查记录[-1] if 审查记录 else None
    下一步 = state.get("下一步行动", [])

    篇章名, 篇章进度, 篇章总数 = get_chapter_info(已完成, 总集数)

    # ───── 渲染 ─────
    width = 64
    print()
    print("╔" + "═" * (width - 2) + "╗")
    title = f"《{片名}》进度看板 — {项目代号}"
    print(f"║  {title:<{width-4}}║")
    print(f"║  {datetime.now().strftime('%Y-%m-%d %H:%M'):<{width-4}}║")
    print("╠" + "═" * (width - 2) + "╣")

    print(f"║  {'总进度:':<10}{make_progress_bar(完成度, 30):<{width-13}}║")
    print(f"║  {'集数:':<10}{f'{已完成}/{总集数} 集 完成':<{width-13}}║")
    print(f"║  {'镜头:':<10}{f'{已完成镜头}/{目标镜头} 个镜头':<{width-13}}║")
    print(f"║  {'当前篇章:':<10}{f'{篇章名} — {篇章进度}/{篇章总数}':<{width-14}}║")
    print(f"║  {'圣经版本:':<10}{圣经版本:<{width-14}}║")
    print(f"║  {'进行中:':<10}{f'{进行中} 集':<{width-13}}║")

    print("╠" + "═" * (width - 2) + "╣")
    print(f"║  工时统计                                                  ║")
    print(f"║    本月预算: {本月预算}h  已用: {本月已用}h  完成: {本月完成集} 集" + " " * 10 + "║")
    if 本月预算 > 0:
        本月进度 = 本月已用 / 本月预算 * 100
        print(f"║    {make_progress_bar(min(本月进度, 100), 25):<{width-7}}║")
    if 本月完成集 > 0 and 本月已用 > 0:
        平均工时 = 本月已用 / 本月完成集
        节奏 = "正常"
        if 平均工时 > 12:
            节奏 = "🔴 严重超时"
        elif 平均工时 > 10:
            节奏 = "🟡 略超时"
        elif 平均工时 < 8:
            节奏 = "🟢 高效"
        print(f"║    平均单集: {平均工时:.1f}h  节奏: {节奏:<25}║"[:width+2])

    print("╠" + "═" * (width - 2) + "╣")
    print(f"║  资产状态                                                  ║")
    print(f"║    角色基因: {角色基因数} 个                                          ║"[:width+2])
    print(f"║    服装模块: {服装模块数} 个                                          ║"[:width+2])
    print(f"║    场景模块: {场景模块数} 个                                          ║"[:width+2])
    print(f"║    法器模块: {法器模块数} 个                                          ║"[:width+2])

    print("╠" + "═" * (width - 2) + "╣")
    总todo = len(todos)
    if 总todo > 0:
        print(f"║  TODO 列表(共 {总todo} 项,高 {len(高优)} 中 {len(中优)} 低 {len(低优)})")
        for t in 高优[:3]:
            ID = t.get("ID", "?")
            obj = t.get("对象", "?")[:35]
            print(f"║    [高] {ID}: {obj:<35}    ║"[:width+2])
        if len(高优) > 3:
            print(f"║    ... 还有 {len(高优)-3} 个高优 TODO")
        for t in 中优[:2]:
            ID = t.get("ID", "?")
            obj = t.get("对象", "?")[:35]
            print(f"║    [中] {ID}: {obj:<35}    ║"[:width+2])
    else:
        print(f"║  TODO 列表: 空                                            ║"[:width+2])

    if 最近审查:
        print("╠" + "═" * (width - 2) + "╣")
        print(f"║  最近跨集审查                                              ║"[:width+2])
        审查日期 = 最近审查.get("审查日期", "?")
        审查范围 = 最近审查.get("审查范围", "?")
        问题数 = 最近审查.get("问题数量", 0)
        print(f"║    {审查日期} / {审查范围}                          ║"[:width+2])
        print(f"║    发现问题: {问题数} 个                                       ║"[:width+2])

    print("╠" + "═" * (width - 2) + "╣")
    if 下一步:
        print(f"║  下一步行动                                                ║"[:width+2])
        for action in 下一步[:3]:
            line = f"    ▶ {action[:50]}"
            print(f"║  {line:<{width-4}}║")

    print("╚" + "═" * (width - 2) + "╝")
    print()

    # 红线检查
    红线 = []
    if len(高优) > 5:
        红线.append(f"🔴 高优 TODO 累积过多({len(高优)} > 5)")
    if 已完成 >= 5 and not 审查记录:
        红线.append(f"🔴 已完成 {已完成} 集但未做过跨集审查")
    elif 审查记录:
        last_audit = 审查记录[-1]
        import re
        match = re.search(r'(\d+)-(\d+)', last_audit.get("审查范围", ""))
        if match:
            gap = 已完成 - int(match.group(2))
            if gap >= 5:
                红线.append(f"🔴 跨集审查超期({gap} 集未审)")
    if 本月完成集 > 0 and 本月已用 / 本月完成集 > 12:
        红线.append(f"🔴 单集平均工时超 12h")

    if 红线:
        print("⚠️  红线警报:")
        for r in 红线:
            print(f"   {r}")
        print("   建议先处理红线问题再继续做新集")
        print()
    else:
        if 已完成 > 0:
            print("✅ 无红线,可以继续做下一集\n")


if __name__ == "__main__":
    main()
