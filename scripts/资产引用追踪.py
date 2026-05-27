#!/usr/bin/env python3
"""
资产引用追踪.py — 资产使用频率追踪

用法:
    cd 项目根目录
    python3 /path/to/资产引用追踪.py [--scan]

    不带参数: 显示当前追踪状态
    --scan: 扫描所有单集大纲,自动更新 资产引用追踪.json

功能:
    1. 扫描每集大纲,统计每个资产被哪些集引用
    2. 维护 资产引用追踪.json
    3. 检查"资产闲置"和"资产即将引入但未建"
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime


def load_json(path):
    if not Path(path).exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def scan_outline_for_assets(outline_path):
    """从单集大纲里抓所有 ID"""
    if not outline_path.exists():
        return set()
    with open(outline_path, 'r', encoding='utf-8') as f:
        text = f.read()
    pattern = r'\b(CHAR-[A-Z0-9]+|OUTFIT-[A-Z0-9]+|PROP-[A-Z0-9-]+|LOC-[A-Z0-9-]+|SPELL-[A-Z0-9-]+|VEHICLE-[A-Z0-9-]+)\b'
    return set(re.findall(pattern, text))


def scan_all_episodes():
    """扫描所有单集大纲,生成资产引用映射"""
    project_root = Path(".")
    outline_dir = project_root / "04_单集大纲"
    if not outline_dir.exists():
        print("❌ 找不到 04_单集大纲 目录")
        return {}

    asset_usage = {}

    for ep_dir in sorted(outline_dir.iterdir()):
        if not ep_dir.is_dir() or not ep_dir.name.startswith("EP"):
            continue
        ep_num = int(ep_dir.name[2:])
        outline_path = ep_dir / "大纲.md"
        if not outline_path.exists():
            continue
        ids = scan_outline_for_assets(outline_path)
        for asset_id in ids:
            if asset_id not in asset_usage:
                asset_usage[asset_id] = {
                    "首次出现": ep_num,
                    "已使用集": [],
                    "总使用次数": 0
                }
            if ep_num not in asset_usage[asset_id]["已使用集"]:
                asset_usage[asset_id]["已使用集"].append(ep_num)
                asset_usage[asset_id]["总使用次数"] += 1

    for asset_id, info in asset_usage.items():
        info["已使用集"] = sorted(info["已使用集"])
        info["首次出现"] = min(info["已使用集"]) if info["已使用集"] else None
        info["最近使用"] = max(info["已使用集"]) if info["已使用集"] else None

    return asset_usage


def check_unbuilt_assets(usage, genome_dir, asset_dir):
    """检查"被引用但未建模块"的资产"""
    built_ids = set()

    if genome_dir.exists():
        for char_dir in genome_dir.iterdir():
            if char_dir.is_dir():
                built_ids.add(char_dir.name)

    if asset_dir.exists():
        for category in asset_dir.iterdir():
            if category.is_dir():
                for asset in category.iterdir():
                    if asset.is_dir():
                        built_ids.add(asset.name)

    referenced_ids = set(usage.keys())
    unbuilt = referenced_ids - built_ids
    return unbuilt, built_ids


def render_dashboard(usage, current_ep, unbuilt, built_ids):
    print()
    print("█" * 60)
    print(f"  资产引用追踪 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("█" * 60)
    print()

    if not usage:
        print("  ℹ️  尚未扫描到任何资产引用")
        return

    by_category = {}
    for asset_id in usage:
        category = asset_id.split('-')[0]
        by_category.setdefault(category, []).append(asset_id)

    for category, ids in sorted(by_category.items()):
        print(f"\n┌─ {category} ─────────────────────────────────────")
        for asset_id in sorted(ids):
            info = usage[asset_id]
            首次 = info.get("首次出现")
            最近 = info.get("最近使用")
            总次数 = info.get("总使用次数", 0)
            状态 = "✅" if asset_id in built_ids else "❌"

            gap = current_ep - 最近 if 最近 else 0
            warning = ""
            if gap >= 5:
                warning = f"⚠️  闲置 {gap} 集"

            print(f"│  {状态} {asset_id:<25} 首:{首次:>2}  末:{最近:>2}  共:{总次数:>3} {warning}")
        print("└" + "─" * 50)

    if unbuilt:
        print()
        print("⚠️  以下资产被大纲引用,但还没建模块:")
        for asset_id in sorted(unbuilt):
            info = usage[asset_id]
            首次 = info.get("首次出现")
            urgency = ""
            gap = 首次 - current_ep if 首次 else 0
            if gap < 0:
                urgency = "🔴 已逾期(过去集已用到)"
            elif gap <= 3:
                urgency = f"🟡 紧急(还有 {gap} 集就要用)"
            else:
                urgency = f"🟢 计划中(还有 {gap} 集准备时间)"
            print(f"    {asset_id}: 首次出现 EP{首次:02d}  {urgency}")
        print()


def main():
    project_root = Path(".")
    state_path = project_root / "项目状态.json"
    tracker_path = project_root / "资产引用追踪.json"

    if not state_path.exists():
        print("❌ 找不到 项目状态.json,请在项目根目录运行")
        sys.exit(1)

    state = load_json(state_path)
    current_ep = state.get("进度概览", {}).get("已完成集数", 0)
    if state.get("各集状态"):
        active_eps = [int(k) for k, v in state["各集状态"].items() if v.get("状态") == "进行中"]
        if active_eps:
            current_ep = max(current_ep, max(active_eps))

    do_scan = "--scan" in sys.argv

    if do_scan or not tracker_path.exists():
        print("🔍 扫描单集大纲...")
        usage = scan_all_episodes()
        save_json(tracker_path, usage)
        print(f"✅ 已扫描完成,登记 {len(usage)} 个资产")
    else:
        usage = load_json(tracker_path) or {}

    unbuilt, built_ids = check_unbuilt_assets(
        usage,
        project_root / "02_角色基因库",
        project_root / "03_资产模块库"
    )

    render_dashboard(usage, current_ep, unbuilt, built_ids)

    print()
    print("─" * 60)
    print(f"总资产数: {len(usage)}")
    print(f"已建模块: {len(built_ids & set(usage.keys()))}")
    print(f"未建模块: {len(unbuilt)}")
    if usage:
        闲置 = [aid for aid, info in usage.items()
                if info.get("最近使用") and current_ep - info["最近使用"] >= 5]
        print(f"闲置资产(≥5 集未用): {len(闲置)}")
    print()
    print("提示: 加 --scan 参数可重新扫描所有大纲")
    print()


if __name__ == "__main__":
    main()
