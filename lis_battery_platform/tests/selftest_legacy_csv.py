# -*- coding: utf-8 -*-
"""
真实历史 CSV 兼容性测试
======================
把项目现有的 solid_data.csv / liquid_data.csv（平台此前一直在用的数据）
走一遍完整导入链路，验证：
  * 现有表头能被正确映射到新数据模型
  * 600 / 650 条历史数据 100% 通过校验、零拒收
  * 导入后可直接计算指标且一致性自检通过
"""
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

TMP_DB = os.path.join(tempfile.gettempdir(), "bf_legacy.db")
for suffix in ("", "-wal", "-shm"):
    if os.path.exists(TMP_DB + suffix):
        os.remove(TMP_DB + suffix)
os.environ["BF_DB_PATH"] = TMP_DB

import pandas as pd                     # noqa: E402
import db, importer, metrics           # noqa: E402
from importer import ImportConfig       # noqa: E402
from metrics import CalcConfig          # noqa: E402
from schema import LIQUID, SOLID        # noqa: E402

ok = True


def check(name, cond, detail=""):
    global ok
    ok = ok and bool(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main():
    db.init_db()
    src = {"液态": (os.path.join(PKG, "liquid_data.csv"), LIQUID, 650),
           "固态": (os.path.join(PKG, "solid_data.csv"), SOLID, 600)}

    for label, (path, bt, expect) in src.items():
        print(f"\n=== {label}：{os.path.basename(path)} ===")
        raw = pd.read_csv(path)
        rep = importer.import_file(open(path, "rb").read(), os.path.basename(path),
                                   ImportConfig(battery_type="auto", dedupe="skip"))
        for line in rep.summary_lines():
            print("      " + line)
        check(f"{label} 表头全部识别", not rep.missing_columns, str(rep.missing_columns))
        check(f"{label} 无未识别列", not rep.unmapped_columns, str(rep.unmapped_columns)[:200])
        check(f"{label} 体系判定", rep.battery_type == bt, rep.battery_type)
        check(f"{label} 行数={expect}", rep.total_rows == expect,
              f"{rep.total_rows}（源 {len(raw)} 行）")
        check(f"{label} 零拒收", rep.invalid_rows == 0,
              f"拒收 {rep.invalid_rows}")
        check(f"{label} 全部入库", rep.inserted_rows == expect,
              f"inserted={rep.inserted_rows}")
        if rep.warnings:
            codes = {}
            for w in rep.warnings:
                codes[w.code] = codes.get(w.code, 0) + 1
            print(f"      警告统计：{codes}")
            for w in rep.warnings[:3]:
                print(f"      样例：行{w.row_no} {w.code} {w.message}")

    print("\n=== 指标计算（历史数据全量）===")
    for bt, label in ((LIQUID, "液态"), (SOLID, "固态")):
        samples = db.fetch_samples(bt)
        res = metrics.run_metrics(samples, bt, CalcConfig(config_name="历史数据"),
                                  note=f"legacy {label}")
        wide = res["wide"]
        print(f"      {label}：{res['sample_count']} 样品 / {res['result_count']} 结果")
        print("      综合评分 均值 %.2f｜中位 %.2f｜最大 %.2f" % (
            wide["composite_score"].mean(), wide["composite_score"].median(),
            wide["composite_score"].max()))
        if "areal_capacity" in wide.columns:
            print("      面容量 均值 %.3f mAh/cm²" % wide["areal_capacity"].mean())
        if "asr" in wide.columns:
            print("      面比电阻 均值 %.2f Ω·cm²" % wide["asr"].mean())
        check(f"{label} 结果非空", res["result_count"] > 0)
        check(f"{label} 评分在 0~100",
              wide["composite_score"].dropna().between(0, 100).all())

    print("\n=== 一致性自检 ===")
    for c in db.verify_consistency():
        print(f"      [{c['status']}] {c['check']} — {c['detail']}")
        check(f"一致性: {c['check']}", c["status"] == "OK", c["detail"])

    print(f"\n库统计：{db.db_summary()}")
    print(f"测试库：{TMP_DB}")
    print("\n结果：", "全部通过" if ok else "存在失败")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
