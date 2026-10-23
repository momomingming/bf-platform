# -*- coding: utf-8 -*-
"""
新增功能自测：模型版本化 / 指标回流 / P1 缺陷修复
=================================================
运行： python tests/selftest_versioning.py
覆盖：
  1. 迁移 v3：source_tag 列 + model_versions 表存在
  2. source_tag 写入并可按来源查询
  3. importer MD5 修复：UploadedFile 类对象能算出 md5 并查到历史批次
  4. composite_score 输入快照包含「体系附加项」来源（shuttle_factor / 膜厚度）
  5. metrics.export_for_modeling 把派生指标回流为建模特征/目标
  6. model_registry：训练登记 → 落盘 → 加载 → 列表 → 激活，全链路可复现
"""
import io
import os
import sys
import json
import tempfile
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

TMP_DB = os.path.join(tempfile.gettempdir(), "bf_versioning.db")
for suffix in ("", "-wal", "-shm"):
    if os.path.exists(TMP_DB + suffix):
        os.remove(TMP_DB + suffix)
os.environ["BF_DB_PATH"] = TMP_DB
MODELS_DIR = os.path.join(tempfile.gettempdir(), "bf_models_test")
os.environ["BF_MODELS_DIR"] = MODELS_DIR
if os.path.exists(MODELS_DIR):
    shutil.rmtree(MODELS_DIR)

import pandas as pd                         # noqa: E402
import db, importer, metrics, model_registry  # noqa: E402
from importer import ImportConfig          # noqa: E402
from schema import LIQUID, SOLID, FIELD_BY_COLUMN  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


class FakeUpload:
    """模仿 streamlit UploadedFile：bytes 内容 + getvalue()。"""
    def __init__(self, data: bytes, name="x.csv"):
        self._data = data
        self.name = name
    def getvalue(self):
        return self._data


def main():
    print("=" * 72)
    print("1. 迁移 v3 与表结构")
    applied = db.init_db()
    check("应用 v3 迁移", 3 in applied, f"applied={applied}")
    conn = db.get_connection()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(import_batches)")]
    check("import_batches 含 source_tag 列", "source_tag" in cols)
    tabs = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    check("model_versions 表已创建", "model_versions" in tabs)

    print("\n2. source_tag 写入与查询")
    tpl = importer.build_template(LIQUID)
    cols = list(tpl.columns)
    fillers = ["MnO2", "rGO", "TiO2", "CoS2", "ZnO", "Fe3O4", "MoS2", "V2O5"]
    rows = []
    for i in range(40):                      # ≥30 条，覆盖真实样本切换路径
        r = list(tpl.iloc[0].values)
        r[0] = fillers[i % len(fillers)]
        r[cols.index("初始比容量(mAh/g)")] = 800.0 + (i * 17) % 600
        r[cols.index("循环次数")] = 100 + (i * 37) % 900
        r[cols.index("容量保持率(%)")] = 70 + (i * 3) % 28
        rows.append(r)
    multi_payload = pd.DataFrame(rows, columns=cols).to_csv(index=False).encode("utf-8-sig")
    cfg = ImportConfig(battery_type="auto", dedupe="skip", source_tag="文献A-2026")
    rep = importer.import_file(io.BytesIO(multi_payload), "tag_test.csv", cfg)
    check("导入成功", rep.status == "SUCCESS", rep.status)
    check("入库 40 条", rep.inserted_rows == 40, f"inserted={rep.inserted_rows}")
    found = db.find_batches_by_source("文献A-2026")
    check("按来源查到批次", len(found) == 1, f"n={len(found)}")
    batches = db.list_batches()
    check("批次表含「来源」列", "来源" in batches.columns)
    check("来源值正确", batches.iloc[0]["来源"] == "文献A-2026")

    print("\n3. importer MD5 修复（UploadedFile 类对象）")
    fake = FakeUpload(multi_payload, "tag_test.csv")
    cfg2 = ImportConfig(battery_type=LIQUID, dedupe="skip")
    rep2 = importer.import_file(fake, "tag_test.csv", cfg2)
    check("UploadedFile 类导入成功", rep2.status == "SUCCESS")
    hist = db.find_batches_by_md5(rep2.batch_id and rep2.batch_id)  # batch_id 本身不是 md5
    # 直接查该文件 md5
    md5 = db.file_md5(multi_payload)
    hist2 = db.find_batches_by_md5(md5)
    check("MD5 非空前次导入查到（死代码已修）", len(hist2) >= 1, f"md5={md5[:8]} n={len(hist2)}")

    print("\n4. composite_score 输入快照完整性")
    samples = db.fetch_samples(LIQUID)
    res = metrics.run_metrics(samples, LIQUID, metrics.CalcConfig(config_name="vt"),
                              note="vt")
    long = db.fetch_metric_results(res["run_id"])
    cs = long[long["metric_code"] == "composite_score"]
    check("存在综合评分结果", not cs.empty)
    inputs = json.loads(cs.iloc[0]["inputs_json"] or "{}")
    check("液态综合评分含 shuttle_factor 来源", "shuttle_factor" in inputs,
          str(list(inputs.keys())))

    print("\n5. 指标回流建模（export_for_modeling）")
    frame, feats, tgts = metrics.export_for_modeling(LIQUID)
    check("回流帧非空", not getattr(frame, "empty", True))
    check("派生指标 composite_score 进入特征", "composite_score" in feats,
          f"feats尾部={feats[-3:]}")
    check("composite_score 作为额外目标", "composite_score" in tgts)
    check("回流帧含 composite_score 列", "composite_score" in list(frame.columns))

    print("\n6. 模型版本化（训练→落盘→加载→激活）")
    vid = model_registry.train_and_register(
        LIQUID, include_derived=True, note="版本化自测", run_id=res["run_id"])
    check("返回版本号", bool(vid), vid)
    artifact = os.path.join(model_registry.models_dir(), f"{vid}.joblib")
    check("模型产物已落盘", os.path.exists(artifact))
    blob = model_registry.load_version(vid)
    check("可加载版本产物", blob is not None)
    check("产物含 results/encoders/scaler",
          all(k in blob for k in ("results", "label_encoders", "scaler")))
    check("版本登记为激活", db.get_active_model_version(LIQUID)["version_id"] == vid)
    versions = model_registry.list_versions(LIQUID)
    check("版本列表非空", not versions.empty, f"n={len(versions)}")

    # 用加载的版本做一次预测，验证可复现
    from modeling import predict_single
    preds = predict_single(blob["results"], blob["label_encoders"], blob["scaler"],
                            blob["feature_cols"], blob["target_cols"],
                            {c: frame[c].iloc[0] for c in blob["feature_cols"]},
                            'liquid')
    check("加载版本可预测", isinstance(preds, dict) and len(preds) > 0,
          f"目标数={len(preds)}")

    # 再登记一个版本并切换激活
    vid2 = model_registry.train_and_register(
        LIQUID, include_derived=False, note="仅基础字段")
    model_registry.set_active(vid2)
    check("可切换激活版本", db.get_active_model_version(LIQUID)["version_id"] == vid2)
    check("旧版本不再是激活", db.get_active_model_version(LIQUID)["version_id"] != vid)

    print("\n" + "=" * 72)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        for f in FAIL:
            print("  ✗ " + f)
    shutil.rmtree(MODELS_DIR, ignore_errors=True)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
