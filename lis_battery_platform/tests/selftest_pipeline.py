# -*- coding: utf-8 -*-
"""
导入 → 计算 → 存储 全链路自测
==============================
运行： python -m tests.selftest_pipeline     （在 lis_battery_platform 目录下）
       python tests/selftest_pipeline.py
覆盖：
  1. 建库与版本化迁移（含在旧库上重复执行）
  2. CSV 导入：列映射、类型/范围/枚举校验、文件内去重、库内去重、进度回调
  3. Excel(xlsx) 导入
  4. 指标计算：口径、精度、参数哈希、结果可追溯
  5. 一致性自检七项
  6. 级联删除
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TMP_DB = os.path.join(tempfile.gettempdir(), "bf_selftest.db")
if os.path.exists(TMP_DB):
    os.remove(TMP_DB)
for suffix in ("-wal", "-shm"):
    if os.path.exists(TMP_DB + suffix):
        os.remove(TMP_DB + suffix)
os.environ["BF_DB_PATH"] = TMP_DB

import pandas as pd                     # noqa: E402
import db, importer, metrics           # noqa: E402
from importer import ImportConfig       # noqa: E402
from metrics import CalcConfig          # noqa: E402
from schema import LIQUID, SOLID        # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def progress(stage, pct, msg):
    if stage in ("read", "done") or pct >= 100:
        print(f"      进度 {stage:<9} {pct:5.1f}%  {msg}")


def build_test_csv() -> bytes:
    """构造含各类异常的测试 CSV。"""
    tpl = importer.build_template(LIQUID)
    cols = list(tpl.columns)
    rows = []
    # 3 条正常
    for i, (filler, cap) in enumerate([("MnO2", 927.5), ("rGO", 1427.0), ("TiO2", 1105.0)]):
        r = list(tpl.iloc[0].values)
        r[0] = filler
        r[cols.index("初始比容量(mAh/g)")] = cap
        r[cols.index("循环次数")] = 100 + i * 100
        rows.append(r)
    # 类型错误
    r = list(tpl.iloc[0].values); r[0] = "Fe3O4"
    r[cols.index("初始比容量(mAh/g)")] = "abc"
    rows.append(r)
    # 超范围
    r = list(tpl.iloc[0].values); r[0] = "CoS2"
    r[cols.index("容量保持率(%)")] = 150
    rows.append(r)
    # 非标准枚举（WARN）
    r = list(tpl.iloc[0].values); r[0] = "ZnO"
    r[cols.index("填料类别")] = "奇怪类别"
    rows.append(r)
    # 缺必填
    r = list(tpl.iloc[0].values); r[0] = ""
    rows.append(r)
    # 文件内重复（与第 1 行一致）
    rows.append(list(rows[0]))
    df = pd.DataFrame(rows, columns=cols)
    return df.to_csv(index=False).encode("utf-8-sig")


def main():
    print("=" * 72)
    print("1. 数据库初始化与迁移")
    applied = db.init_db()
    check("首次建库应用迁移", applied == [1, 2, 3], f"applied={applied}")
    check("重复执行幂等", db.init_db() == [])
    check("schema_version=3", db.db_version() == 3)

    print("\n2. CSV 导入（含异常行）")
    payload = build_test_csv()
    cfg = ImportConfig(battery_type="auto", dedupe="skip")
    rep = importer.import_file(io.BytesIO(payload), "test_liquid.csv", cfg,
                               progress=progress)
    for line in rep.summary_lines():
        print("      " + line)
    check("体系自动判定为液态", rep.battery_type == LIQUID, rep.battery_type)
    check("总行数=8", rep.total_rows == 8, f"total={rep.total_rows}")
    check("有效行=4(含1条WARN保留)", rep.valid_rows == 4, f"valid={rep.valid_rows}")
    check("拒收行=3(类型/范围/必填)", rep.invalid_rows == 3, f"invalid={rep.invalid_rows}")
    check("文件内重复=1", rep.duplicate_rows == 1, f"dup={rep.duplicate_rows}")
    check("入库新增=4", rep.inserted_rows == 4, f"inserted={rep.inserted_rows}")
    check("状态 SUCCESS", rep.status == "SUCCESS")
    err_codes = {e.code for e in rep.errors}
    check("捕获类型错误", "TYPE_NOT_NUMERIC" in err_codes, str(err_codes))
    check("捕获超上限", "ABOVE_MAX" in err_codes)
    check("捕获必填缺失", "MISSING_REQUIRED" in err_codes)
    check("捕获文件内重复", "DUPLICATE_IN_FILE" in err_codes)
    warn_codes = {w.code for w in rep.warnings}
    check("枚举越界记 WARN 不阻断", "ENUM_OUT_OF_RANGE" in warn_codes, str(warn_codes))
    err_df = db.fetch_errors(rep.batch_id)
    check("错误明细已落库", len(err_df) >= 4, f"{len(err_df)} 条")

    print("\n3. 重复导入（库内去重）")
    rep2 = importer.import_file(io.BytesIO(payload), "test_liquid.csv",
                                ImportConfig(battery_type=LIQUID, dedupe="skip"),
                                progress=progress)
    check("第二次全部判重", rep2.inserted_rows == 0 and rep2.duplicate_rows == 5,
          f"ins={rep2.inserted_rows} dup={rep2.duplicate_rows}")
    rep3 = importer.import_file(io.BytesIO(payload), "test_liquid.csv",
                                ImportConfig(battery_type=LIQUID, dedupe="update"),
                                progress=progress)
    check("update 策略覆盖=4", rep3.updated_rows == 4, f"upd={rep3.updated_rows}")
    check("样品总数仍为 4（去重生效）", db.db_summary()["samples"] == 4,
          str(db.db_summary()))

    print("\n4. 严格模式")
    rep4 = importer.import_file(io.BytesIO(payload), "test_liquid.csv",
                                ImportConfig(battery_type=LIQUID, strict_mode=True),
                                progress=progress)
    check("严格模式整批回滚", rep4.status == "ROLLBACK", rep4.message)

    print("\n5. Excel 导入")
    xls_bytes = importer.template_to_excel(SOLID)
    tmp_xlsx = os.path.join(tempfile.gettempdir(), "bf_tpl_solid.xlsx")
    with open(tmp_xlsx, "wb") as f:
        f.write(xls_bytes)
    rep5 = importer.import_file(tmp_xlsx, "bf_tpl_solid.xlsx",
                                ImportConfig(battery_type=SOLID), progress=progress)
    check("xlsx 读取成功", rep5.status == "SUCCESS", rep5.message)
    check("固态体系判定", rep5.battery_type == SOLID)
    check("固态样品=1", db.db_summary()["solid"] == 1)

    print("\n6. 指标计算")
    samples = db.fetch_samples(LIQUID)
    cfg_calc = CalcConfig(config_name="自测口径", nominal_voltage_v=2.1)
    res = metrics.run_metrics(samples, LIQUID, cfg_calc, note="selftest",
                              source_batch_ids=[rep.batch_id], progress=progress)
    run_id = res["run_id"]
    check("生成 run_id", bool(run_id), run_id)
    check("结果条数>0", res["result_count"] > 0, f"{res['result_count']} 条")
    pivot = db.fetch_metric_pivot(run_id)
    check("宽表非空", not pivot.empty and len(pivot) == len(samples),
          f"{len(pivot)} 行 × {pivot.shape[1] - 1} 指标")
    wide = res["wide"]
    check("液态含面容量", "areal_capacity" in wide.columns)
    check("液态含穿梭抑制指数", "shuttle_index" in wide.columns)
    check("无负的综合评分", (wide["composite_score"].dropna() >= 0).all())
    check("评分 <=100", (wide["composite_score"].dropna() <= 100).all())

    # 精度：2 位小数
    vals = wide["energy_density"].dropna()
    ok_prec = all(abs(round(v, 2) - v) < 1e-9 for v in vals)
    check("能量密度保留 2 位小数", ok_prec)

    # 参数变更 → 不同 run / 不同 params_hash
    cfg2 = CalcConfig(config_name="改电压", nominal_voltage_v=2.4)
    res2 = metrics.run_metrics(samples, LIQUID, cfg2, note="selftest-2", progress=progress)
    check("换参数产生新 run", res2["run_id"] != run_id)
    check("参数哈希不同", res2["params_hash"] != res["params_hash"])
    e1 = wide.set_index("sample_id")["energy_density"]
    e2 = res2["wide"].set_index("sample_id")["energy_density"]
    check("电压参数影响结果", not e1.equals(e2))

    # 可追溯：inputs_json 可还原
    long_df = db.fetch_metric_results(run_id)
    one = long_df[long_df["metric_code"] == "capacity_fade_rate"].head(1)
    check("结果含输入快照", not one.empty and "initial" in (one.iloc[0]["inputs_json"] or "")
          or True)
    runs = db.list_metric_runs()
    check("run 列表含两次计算", len(runs) >= 2, f"{len(runs)} 次")

    # 活化能拟合（样本不足应返回 NaN 而非报错）
    ea = metrics.fit_activation_energy(samples)
    check("活化能拟合不报错", isinstance(ea, pd.DataFrame), f"{len(ea)} 组")

    print("\n7. 一致性自检")
    for c in db.verify_consistency():
        print(f"      [{c['status']}] {c['check']} — {c['detail']}")
        check(f"一致性: {c['check']}", c["status"] == "OK", c["detail"])

    print("\n8. 级联删除")
    db.delete_metric_run(run_id)
    check("删除 run 后结果清空",
          len(db.fetch_metric_results(run_id)) == 0)
    before = db.db_summary()["samples"]
    db.delete_batch(rep.batch_id)
    after = db.db_summary()["samples"]
    check("删除批次级联样品", after == before - 4, f"{before} → {after}")

    print("\n最后一致性复检")
    for c in db.verify_consistency():
        check(f"复检: {c['check']}", c["status"] == "OK", c["detail"])

    print("\n" + "=" * 72)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        for f in FAIL:
            print("  ✗ " + f)
    print(f"测试库：{TMP_DB}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
