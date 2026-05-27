#!/usr/bin/env python3
"""
一致性检查.py — 80 集长剧项目的自动校验工具

用法:
    cd 项目根目录
    python3 /path/to/一致性检查.py

功能:
    1. 校验 ID 引用完整性(圣经引用的 ID 是否都在基因库/资产库中存在)
    2. 校验版本一致性(单集用的资产版本是否对应正确)
    3. 资产使用频率统计(哪些资产 N 集没用了)
    4. 触发红线警报(单集工时、审查间隔、TODO 累积)
    5. 输出可读报告

输出:
    控制台打印 + 10_跨集审查报告/一致性检查_YYYYMMDD.md
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import re

# ─────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────
RED_LINE_SINGLE_EPISODE_HOURS = 12
RED_LINE_AUDIT_INTERVAL = 5
RED_LINE_HIGH_TODO_COUNT = 5
ASSET_UNUSED_THRESHOLD_EPISODES = 5


# ─────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────
def load_json(path):
    """加载 JSON,失败时返回 None"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON 解析失败: {path}\n   {e}")
        return None


def find_all_genome_jsons(genome_dir):
    """递归找出所有角色基因 JSON"""
    genomes = {}
    if not genome_dir.exists():
        return genomes
    for char_dir in genome_dir.iterdir():
        if char_dir.is_dir():
            json_path = char_dir / f"{char_dir.name}.json"
            data = load_json(json_path)
            if data:
                genomes[char_dir.name] = data
    return genomes


def find_all_asset_jsons(asset_dir):
    """递归找出所有资产模块 JSON"""
    assets = {}
    if not asset_dir.exists():
        return assets
    for category in asset_dir.iterdir():
        if category.is_dir():
            for asset in category.iterdir():
                if asset.is_dir():
                    json_files = list(asset.glob("*.json"))
                    for jf in json_files:
                        if not jf.name.startswith('_'):
                            data = load_json(jf)
                            if data:
                                assets[asset.name] = data
                            break
    return assets


def extract_ids_from_bible(bible_path):
    """从圣经里抓所有 ID 引用"""
    if not bible_path.exists():
        return set()
    with open(bible_path, 'r', encoding='utf-8') as f:
        text = f.read()
    pattern = r'\b(CHAR-[A-Z0-9]+|OUTFIT-[A-Z0-9]+|PROP-[A-Z0-9-]+|LOC-[A-Z0-9-]+|SPELL-[A-Z0-9-]+|VEHICLE-[A-Z0-9-]+)\b'
    return set(re.findall(pattern, text))


# ─────────────────────────────────────────────────────
# 检查项
# ─────────────────────────────────────────────────────
def check_id_completeness(bible_ids, genomes, assets):
    """检查项 1:ID 引用完整性"""
    print("\n" + "═" * 60)
    print("📋 检查项 1:ID 引用完整性")
    print("═" * 60)

    issues = []
    defined_ids = set(genomes.keys()) | set(assets.keys())
    missing = bible_ids - defined_ids

    if missing:
        for mid in sorted(missing):
            print(f"  ❌ 圣经引用了 {mid},但基因库 / 资产库中找不到")
            issues.append({"类型": "ID缺失", "对象": mid})
    else:
        print(f"  ✅ 圣经引用的 {len(bible_ids)} 个 ID 在基因库/资产库中都有定义")

    # 反向检查:基因库/资产库里有,但圣经没引用的(可能是孤儿)
    orphans = defined_ids - bible_ids
    if orphans:
        print(f"  ⚠️  以下 {len(orphans)} 个 ID 已建但圣经未引用(可能是孤儿):")
        for oid in sorted(orphans):
            print(f"      {oid}")

    return issues


def check_asset_usage(state, total_episodes_done):
    """检查项 2:资产使用频率"""
    print("\n" + "═" * 60)
    print("📋 检查项 2:资产使用频率")
    print("═" * 60)

    issues = []
    asset_list = state.get("资产清单", {})
    current_ep = total_episodes_done

    # 查看资产引用追踪(如果有)
    tracker_path = Path("资产引用追踪.json")
    if tracker_path.exists():
        tracker = load_json(tracker_path)
        for asset_id, info in tracker.items():
            used_eps = info.get("已使用集", [])
            if used_eps:
                last_used = max(used_eps)
                gap = current_ep - last_used
                if gap >= ASSET_UNUSED_THRESHOLD_EPISODES:
                    print(f"  ⚠️  {asset_id}:上次使用是 EP{last_used:02d},已 {gap} 集没用")
                    issues.append({
                        "类型": "资产闲置",
                        "对象": asset_id,
                        "未使用集数": gap
                    })
    else:
        print("  ℹ️  未找到 资产引用追踪.json,跳过此项")

    if not issues:
        print("  ✅ 所有资产使用正常,无长期闲置")

    return issues


def check_red_lines(state, total_episodes_done):
    """检查项 3:红线警报"""
    print("\n" + "═" * 60)
    print("📋 检查项 3:红线警报")
    print("═" * 60)

    issues = []

    # 红线 1:单集工时 > 12h
    各集状态 = state.get("各集状态", {})
    for ep, info in 各集状态.items():
        hours = info.get("用时小时", 0)
        if hours > RED_LINE_SINGLE_EPISODE_HOURS:
            print(f"  🔴 红线 1:EP{ep} 工时 {hours}h,超过 {RED_LINE_SINGLE_EPISODE_HOURS}h 上限")
            issues.append({
                "类型": "工时超标",
                "对象": f"EP{ep}",
                "数值": hours
            })

    # 红线 2:跨集审查间隔
    审查记录 = state.get("跨集审查记录", [])
    if 审查记录:
        last_audit = 审查记录[-1]
        audit_range = last_audit.get("审查范围", "")
        match = re.search(r'(\d+)-(\d+)', audit_range)
        if match:
            last_audit_end = int(match.group(2))
            gap = total_episodes_done - last_audit_end
            if gap >= RED_LINE_AUDIT_INTERVAL:
                print(f"  🔴 红线 2:已 {gap} 集未做跨集审查(上次审查到 EP{last_audit_end:02d})")
                issues.append({
                    "类型": "审查超期",
                    "对象": "跨集审查",
                    "数值": gap
                })
            else:
                print(f"  ✅ 跨集审查节奏正常(距上次 {gap} 集)")
    else:
        if total_episodes_done >= RED_LINE_AUDIT_INTERVAL:
            print(f"  🔴 红线 2:已完成 {total_episodes_done} 集,但还没做过跨集审查")
            issues.append({
                "类型": "审查超期",
                "对象": "跨集审查",
                "数值": total_episodes_done
            })

    # 红线 3:高优 TODO 累积
    todos = state.get("TODO列表", [])
    high_todos = [t for t in todos if t.get("优先级") == "高"]
    if len(high_todos) > RED_LINE_HIGH_TODO_COUNT:
        print(f"  🔴 红线 3:高优 TODO 数量 {len(high_todos)},超过 {RED_LINE_HIGH_TODO_COUNT} 个上限")
        issues.append({
            "类型": "TODO 累积",
            "对象": "高优 TODO",
            "数值": len(high_todos)
        })
    elif high_todos:
        print(f"  ⚠️  高优 TODO 数量 {len(high_todos)}(上限 {RED_LINE_HIGH_TODO_COUNT})")
    else:
        print(f"  ✅ 高优 TODO 数量正常")

    return issues


def check_version_consistency(state, genomes):
    """检查项 4:基因版本与篇章对应"""
    print("\n" + "═" * 60)
    print("📋 检查项 4:基因版本与篇章对应")
    print("═" * 60)

    issues = []
    current_chapter = state.get("项目元数据", {}).get("当前篇章", 0)

    for char_id, genome in genomes.items():
        version = genome.get("version", "v?")
        version_log = genome.get("version_log", [])
        print(f"  ℹ️  {char_id}: 当前版本 {version}, 共 {len(version_log)} 个历史版本")

        if current_chapter >= 2 and version == "v1.0":
            print(f"  ⚠️  {char_id} 仍在 v1.0,但当前已到篇章 {current_chapter},可能需要升级")
            issues.append({
                "类型": "版本可能滞后",
                "对象": char_id,
                "当前版本": version,
                "当前篇章": current_chapter
            })

    if not issues:
        print("  ✅ 基因版本与篇章对应正常")

    return issues


# ─────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────
def main():
    project_root = Path(".")
    state_path = project_root / "项目状态.json"

    if not state_path.exists():
        print("❌ 找不到 项目状态.json,请确保在项目根目录运行")
        sys.exit(1)

    state = load_json(state_path)
    if not state:
        print("❌ 项目状态.json 解析失败")
        sys.exit(1)

    项目代号 = state.get("项目元数据", {}).get("项目代号", "未知")
    print("\n" + "█" * 60)
    print(f"  一致性检查 — {项目代号}")
    print(f"  执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("█" * 60)

    bible_files = list((project_root / "01_圣经").glob("圣经_v*.md"))
    if bible_files:
        latest_bible = max(bible_files, key=lambda p: p.name)
        bible_ids = extract_ids_from_bible(latest_bible)
        print(f"\n📖 当前圣经: {latest_bible.name}")
        print(f"   引用的 ID 总数: {len(bible_ids)}")
    else:
        print("\n⚠️  未找到圣经文件")
        bible_ids = set()

    genomes = find_all_genome_jsons(project_root / "02_角色基因库")
    print(f"👥 角色基因: {len(genomes)} 个")

    assets = find_all_asset_jsons(project_root / "03_资产模块库")
    print(f"📦 资产模块: {len(assets)} 个")

    total_eps = state.get("进度概览", {}).get("已完成集数", 0)
    print(f"🎬 已完成集数: {total_eps}")

    all_issues = []
    all_issues.extend(check_id_completeness(bible_ids, genomes, assets))
    all_issues.extend(check_asset_usage(state, total_eps))
    all_issues.extend(check_red_lines(state, total_eps))
    all_issues.extend(check_version_consistency(state, genomes))

    print("\n" + "█" * 60)
    print("  📊 总结")
    print("█" * 60)

    if not all_issues:
        print("  🟢 绿灯 — 一切正常,可以继续做下一集")
    else:
        red_count = sum(1 for i in all_issues if "红线" in str(i) or i.get("类型") in ["工时超标", "审查超期", "TODO 累积"])
        if red_count > 0:
            print(f"  🔴 红灯 — 发现 {len(all_issues)} 个问题(其中 {red_count} 个红线)")
            print(f"     必须处理红线问题后才能继续")
        else:
            print(f"  🟡 黄灯 — 发现 {len(all_issues)} 个警告,建议处理后继续")

    report_dir = project_root / "10_跨集审查报告"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"一致性检查_{datetime.now().strftime('%Y%m%d_%H%M')}.md"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# 一致性检查报告\n\n")
        f.write(f"- 项目: {项目代号}\n")
        f.write(f"- 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- 已完成集数: {total_eps}\n")
        f.write(f"- 圣经引用 ID 数: {len(bible_ids)}\n")
        f.write(f"- 角色基因数: {len(genomes)}\n")
        f.write(f"- 资产模块数: {len(assets)}\n\n")
        f.write(f"## 发现的问题 ({len(all_issues)})\n\n")
        if all_issues:
            for i, issue in enumerate(all_issues, 1):
                f.write(f"### 问题 {i}\n")
                for k, v in issue.items():
                    f.write(f"- {k}: {v}\n")
                f.write("\n")
        else:
            f.write("无问题。\n")

    print(f"\n📝 完整报告: {report_path}")
    print("█" * 60 + "\n")


if __name__ == "__main__":
    main()
