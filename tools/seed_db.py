# -*- coding: utf-8 -*-
"""
灌库脚本（可复现 / 幂等）
========================
把"原本的数据库"(liquid_data.csv / solid_data.csv) 与 策划的文献样本
(lit_samples/*.csv) 灌入 SQLite，统一打 source_tag 以便回溯与按来源筛选。

* 幂等：样品表 content_hash UNIQUE + dedupe="skip"，重复文件/重复行不会重复入库。
* 可复现：本脚本进仓库，服务器拉新代码后跑一次即可把生产库补齐到同一状态。
* 用法：
    # 本地验证（指定一个本地库路径）
    BF_DB_PATH="D:/锂硫电池/bf-platform/lit_extracted/_seed_local.db" python tools/seed_db.py
    # 服务器生产库（BF_DB_PATH 已设为 C:/apps/bf-platform/data/platform.db）
    python tools/seed_db.py
"""
from __future__ import annotations

import json
import os
import sys

PKG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lis_battery_platform")
sys.path.insert(0, os.path.abspath(PKG))

from importer import import_file, ImportConfig  # noqa: E402
from db import db_summary, list_batches            # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def run(path: str, tag: str, btype: str, db_path) -> None:
    if not os.path.exists(path):
        print(f"[跳过] 文件不存在: {path}")
        return
    cfg = ImportConfig(battery_type=btype, source_tag=tag, dedupe="skip")
    rep = import_file(path, os.path.basename(path), cfg, db_path=db_path)
    print(f"\n=== {os.path.basename(path)} [{btype}] tag={tag} ===")
    for line in rep.summary_lines():
        print("  " + line)
    if rep.message:
        print("  备注: " + rep.message)
    if rep.missing_columns:
        print("  缺列(导致失败): " + str(rep.missing_columns))
    # 打印前 3 条错误/警告，便于现场排查
    shown = 0
    for e in (rep.errors + rep.warnings):
        if shown >= 3:
            break
        print("  -", e.severity, e.code, f"行{e.row_no}", e.message)
        shown += 1
    if (rep.errors or rep.warnings) and shown == 0:
        print("  (无明细)")


def main() -> None:
    db_path = os.environ.get("BF_DB_PATH")
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    print("目标数据库:", db_path or "(默认: lis_battery_platform/data/platform.db)")

    # 1) 原本的数据库（用户确认的历史基线）
    run(os.path.join(REPO, "lis_battery_platform", "liquid_data.csv"),
        "legacy_bfplatform_v1", "liquid", db_path)
    run(os.path.join(REPO, "lis_battery_platform", "solid_data.csv"),
        "legacy_bfplatform_v1", "solid", db_path)

    # 2) 策划的文献样本（原创研究 + 宿主明确，可追溯）
    lit = os.path.join(REPO, "lit_samples", "lit_lis_hosts.csv")
    run(lit, "lit_original_2018_2026", "liquid", db_path)

    # 3) 汇总
    print("\n=== DB SUMMARY ===")
    print(json.dumps(db_summary(db_path), ensure_ascii=False, indent=2))
    print("\n=== 最近批次 ===")
    batches = list_batches(db_path, limit=10)
    if not batches.empty:
        print(batches.to_string(index=False))


if __name__ == "__main__":
    main()
