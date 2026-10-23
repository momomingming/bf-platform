# -*- coding: utf-8 -*-
"""
Streamlit 面板：数据导入（Tab7）与精细化指标计算（Tab8）
========================================================
只负责 UI 编排，业务规则一律调用 importer / metrics / db，
保证「界面上看到的口径」与「后台实际执行的口径」是同一份代码。
"""
from __future__ import annotations

import json
from typing import Optional

import pandas as pd
import streamlit as st

import db
import importer
import metrics
import model_registry
from importer import ImportConfig
from metrics import CalcConfig
from schema import (BATTERY_TYPE_CN, FIELD_BY_COLUMN, FIELD_SPECS,
                    LIQUID, SOLID)

BT_OPTIONS = {"自动判定": "auto", "液态锂硫电池": LIQUID, "固态锂硫电池": SOLID}


def _sub(title: str):
    st.markdown(f'<div class="sub-header">{title}</div>', unsafe_allow_html=True)


# ============================================================
# Tab 7：批量数据导入
# ============================================================
def render_import_panel():
    _sub("📥 批量数据导入 — 解析 / 校验 / 去重 / 落库")
    db.init_db()

    # ---------- ① 模板 ----------
    with st.expander("① 下载导入模板（推荐先下载对照列名）", expanded=False):
        c1, c2 = st.columns(2)
        for col, bt in ((c1, LIQUID), (c2, SOLID)):
            label = BATTERY_TYPE_CN[bt]
            with col:
                st.caption(f"{label} · {len([s for s in FIELD_SPECS if bt in s.applies_to])} 个标准字段")
                st.download_button(
                    f"⬇️ CSV 模板（{label}）",
                    data=importer.build_template(bt).to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"import_template_{bt}.csv",
                    mime="text/csv", width="stretch")
                st.download_button(
                    f"⬇️ Excel 模板（{label}）",
                    data=importer.template_to_excel(bt),
                    file_name=f"import_template_{bt}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch")
        st.caption("支持常见别名表头（如「比表面积」「BET」「SSA」互通），"
                   "编码自动探测 UTF-8 / GBK，分隔符自动探测逗号 / 制表符 / 分号。")

    # ---------- ② 上传与选项 ----------
    st.markdown("#### ② 上传文件")
    files = st.file_uploader(
        "支持 CSV / TSV / TXT / Excel（xlsx、xls），可一次选多个文件",
        type=["csv", "tsv", "txt", "xlsx", "xlsm", "xls"],
        accept_multiple_files=True, key="imp_files")

    o1, o2, o3, o4 = st.columns([1.2, 1.3, 1.0, 1.0])
    with o1:
        bt_opt = st.selectbox("电池体系", list(BT_OPTIONS.keys()), index=0)
    with o2:
        dedupe_opt = st.selectbox("重复数据处理",
                                  ["跳过（保留库中已有）", "覆盖更新（以新数据为准）"],
                                  index=0)
    with o3:
        strict_opt = st.checkbox(
            "严格模式", value=False,
            help="开启后，只要文件中有任意一行校验失败，整批数据都不入库")
    with o4:
        sheet_opt = st.text_input("Excel 工作表名", value="", placeholder="留空=第1个")

    run_import = st.button("🚀 开始导入", type="primary",
                           width="stretch", disabled=not files)

    if run_import and files:
        cfg = ImportConfig(
            battery_type=BT_OPTIONS[bt_opt],
            dedupe="skip" if dedupe_opt.startswith("跳过") else "update",
            strict_mode=strict_opt,
            sheet_name=(sheet_opt.strip() or None))
        for f in files:
            _import_one(f, cfg)
        st.rerun()

    # ---------- ③ 批次历史 ----------
    st.markdown("#### ③ 导入批次")
    batches = db.list_batches()
    if batches.empty:
        st.info("尚无导入记录。上传文件后点击「开始导入」。")
    else:
        st.dataframe(batches, width="stretch", hide_index=True,
                     height=min(300, 36 * len(batches) + 38))
        with st.expander("🗑️ 删除批次（连带删除该批次样品与其计算结果）"):
            bid = st.selectbox("选择批次", batches["batch_id"].tolist(),
                               key="del_batch")
            if st.button("确认删除", key="del_batch_btn"):
                info = db.delete_batch(bid)
                st.warning(f"已删除批次 {info['deleted_batch']}，"
                           f"级联删除计算结果 {info['deleted_metric_results']} 条")
                st.rerun()

    # ---------- ④ 错误明细回溯 ----------
    if not batches.empty:
        with st.expander("🔎 查看某批次的错误/警告明细"):
            bid2 = st.selectbox("选择批次", batches["batch_id"].tolist(),
                                key="err_batch")
            sev = st.radio("级别", ["全部", "ERROR", "WARN"], horizontal=True,
                           key="err_sev")
            edf = db.fetch_errors(bid2, None if sev == "全部" else sev)
            if edf.empty:
                st.success("该批次无错误/警告记录")
            else:
                st.dataframe(edf, width="stretch", hide_index=True,
                             height=min(360, 36 * len(edf) + 38))
                st.download_button(
                    "⬇️ 导出明细 CSV",
                    data=edf.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"import_errors_{bid2}.csv",
                    mime="text/csv")

    # ---------- ⑤ 库概览与一致性 ----------
    st.markdown("#### ④ 数据库概览与一致性自检")
    s = db.db_summary()
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("样品总数", s["samples"])
    k2.metric("液态 / 固态", f"{s['liquid']} / {s['solid']}")
    k3.metric("导入批次", s["batches"])
    k4.metric("计算批次", s["metric_runs"])
    k5.metric("指标结果", s["metric_results"])
    st.caption(f"数据库：{s['db_path']}　|　Schema 版本：v{s['schema_version']}")

    if st.button("🧪 运行一致性自检", key="btn_verify"):
        checks = db.verify_consistency()
        cdf = pd.DataFrame([{"检查项": c["check"], "结果": c["status"],
                             "说明": c["detail"]} for c in checks])
        st.dataframe(cdf, width="stretch", hide_index=True)
        if all(c["status"] == "OK" for c in checks):
            st.success("全部通过：导入、计算、存储三环节数据一致")
        else:
            st.error("存在不一致项，请按说明处理（可尝试重新导入或重算）")


def _import_one(f, cfg: ImportConfig):
    st.markdown(f"**{f.name}**")
    bar = st.progress(0)
    status = st.empty()

    def cb(stage, pct, msg, _bar=bar, _st=status):
        _bar.progress(min(max(int(pct), 0), 100))
        _st.caption(f"`{stage}` {pct:.0f}% — {msg}")

    try:
        rep = importer.import_file(f.getvalue(), f.name, cfg, progress=cb)
    except Exception as e:                       # noqa: BLE001
        st.error(f"导入失败：{type(e).__name__}: {e}")
        return

    if rep.status == "SUCCESS":
        st.success("✅ " + "　".join(rep.summary_lines()[2:]))
    elif rep.status == "ROLLBACK":
        st.warning("⏪ " + rep.message)
    else:
        st.error("❌ " + (rep.message or "导入失败"))
        if rep.missing_columns:
            st.write("缺少必填列：", rep.missing_columns)
        return

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("总行数", rep.total_rows)
    m2.metric("有效", rep.valid_rows)
    m3.metric("拒收", rep.invalid_rows)
    m4.metric("重复", rep.duplicate_rows)
    m5.metric("新增 / 更新", f"{rep.inserted_rows} / {rep.updated_rows}")

    if rep.unmapped_columns:
        st.caption(f"未识别列（已忽略）：{rep.unmapped_columns}")
    if rep.warnings:
        with st.expander(f"⚠️ {len(rep.warnings)} 条警告（已入库，建议复核）"):
            wdf = pd.DataFrame([w.as_dict() for w in rep.warnings])
            st.dataframe(wdf, width="stretch", hide_index=True,
                         height=min(300, 36 * len(wdf) + 38))
    if rep.errors:
        with st.expander(f"❌ {len(rep.errors)} 条错误（对应行未入库）"):
            edf = pd.DataFrame([e.as_dict() for e in rep.errors])
            st.dataframe(edf, width="stretch", hide_index=True,
                         height=min(300, 36 * len(edf) + 38))


# ============================================================
# Tab 8：精细化指标计算
# ============================================================
def render_metrics_panel(default_is_liquid: bool = True):
    _sub("🧮 精细化指标计算 — 口径可查 / 参数可调 / 结果可追溯")
    db.init_db()

    # ---------- ① 计算口径 ----------
    with st.expander("① 计算口径说明（公式 / 单位 / 精度 / 版本）", expanded=False):
        st.dataframe(metrics.specs_frame(), width="stretch", hide_index=True)
        st.caption(f"指标定义版本：{metrics.METRIC_VERSION}；"
                   "所有结果统一采用十进制四舍五入（ROUND_HALF_UP）。")

    # ---------- ② 参数配置 ----------
    st.markdown("#### ② 计算参数")
    base = CalcConfig()
    p1, p2, p3 = st.columns(3)
    with p1:
        cfg_name = st.text_input("配置名", value=base.config_name)
        v_nom = st.number_input("标称电压 (V)", 1.0, 4.0, float(base.nominal_voltage_v), 0.05)
        v_theo = st.number_input("理论比容量 (mAh/g)", 500.0, 3000.0,
                                 float(base.theoretical_capacity_mah_g), 5.0)
        v_ref_t = st.number_input("参考温度 (°C)", -20.0, 100.0,
                                  float(base.ref_temperature_c), 1.0)
    with p2:
        v_ea = st.number_input("表观活化能 Ea (eV)", 0.01, 2.0,
                               float(base.activation_energy_ev), 0.01)
        v_eol = st.number_input("寿命终止保持率 (%)", 50.0, 95.0,
                                float(base.eol_retention_pct), 1.0)
        v_maxc = st.number_input("寿命外推上限 (cycles)", 1000, 100000,
                                 int(base.max_est_cycles), 1000)
    with p3:
        v_shuttle = st.number_input("穿梭因子参考值", 0.01, 1.0,
                                    float(base.shuttle_ref), 0.01)
        v_ce_floor = st.number_input("库伦效率评分下限 (%)", 80.0, 99.0,
                                     float(base.ce_floor_pct), 0.5)
        v_cond_floor = st.number_input("电导率归一化下限 (mS/cm)", 0.001, 1.0,
                                       float(base.conductivity_floor_ms_cm), 0.001,
                                       format="%.3f")

    with st.expander("⚖️ 综合评分权重（自动归一化）"):
        w1, w2, w3, w4, w5 = st.columns(5)
        w_cap = w1.slider("容量", 0.0, 1.0, base.weights["capacity"], 0.05)
        w_ret = w2.slider("保持率", 0.0, 1.0, base.weights["retention"], 0.05)
        w_ce = w3.slider("库伦效率", 0.0, 1.0, base.weights["coulombic"], 0.05)
        w_cond = w4.slider("电导率", 0.0, 1.0, base.weights["conductivity"], 0.05)
        w_ext = w5.slider("体系附加项", 0.0, 1.0, base.weights["extra"], 0.05)

    cfg = CalcConfig(
        config_name=cfg_name, nominal_voltage_v=v_nom,
        theoretical_capacity_mah_g=v_theo, ref_temperature_c=v_ref_t,
        activation_energy_ev=v_ea, eol_retention_pct=v_eol,
        max_est_cycles=int(v_maxc), shuttle_ref=v_shuttle,
        ce_floor_pct=v_ce_floor, conductivity_floor_ms_cm=v_cond_floor,
        weights={"capacity": w_cap, "retention": w_ret, "coulombic": w_ce,
                 "conductivity": w_cond, "extra": w_ext})
    st.caption(f"参数指纹（params_hash）：`{db.compute_params_hash(cfg.to_dict())}`"
               "　—— 参数一旦变化即生成新的计算批次，历史结果不被覆盖。")

    # ---------- ③ 选择数据 ----------
    st.markdown("#### ③ 选择数据并执行计算")
    d1, d2, d3 = st.columns([1, 1, 1.2])
    with d1:
        bt_ui = st.radio("电池体系",
                         ["液态锂硫电池", "固态锂硫电池"],
                         index=0 if default_is_liquid else 1, horizontal=False)
        bt = LIQUID if bt_ui == "液态锂硫电池" else SOLID
    with d2:
        batches = db.list_batches()
        opts = ["（全部样品）"]
        if not batches.empty:
            liq_b = batches[batches["体系"] == bt]["batch_id"].tolist()
            opts += liq_b
        sel = st.selectbox("导入批次范围", opts)
    with d3:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        go = st.button("▶️ 执行计算并落库", type="primary", width="stretch")

    samples = db.fetch_samples(bt, None if sel == "（全部样品）" else sel)
    st.caption(f"待计算样品：**{len(samples)}** 条")

    if go:
        if samples.empty:
            st.error("没有可计算的样品。请先在「📥 数据导入」中导入数据，"
                     "或在侧边栏启用内置数据。")
        else:
            bar = st.progress(0)
            stt = st.empty()

            def cb(stage, pct, msg, _b=bar, _s=stt):
                _b.progress(min(max(int(pct), 0), 100))
                _s.caption(f"`{stage}` {pct:.0f}% — {msg}")

            with st.spinner("计算中…"):
                res = metrics.run_metrics(
                    samples, bt, cfg,
                    note=f"UI计算 · {cfg.config_name}",
                    source_batch_ids=None if sel == "（全部样品）" else [sel],
                    progress=cb)
            st.session_state["last_run_id"] = res["run_id"]
            st.success(f"✅ 完成：run_id `{res['run_id']}`，"
                       f"{res['sample_count']} 个样品 / {res['result_count']} 条结果，"
                       f"参数指纹 `{res['params_hash']}`")
            st.rerun()

    # ---------- ④ 结果 ----------
    st.markdown("#### ④ 计算结果")
    runs = db.list_metric_runs()
    if runs.empty:
        st.info("尚无计算记录。配置参数后点击「执行计算并落库」。")
        return

    runs_bt = runs[runs["体系"] == bt]
    if runs_bt.empty:
        st.info(f"{bt_ui} 暂无计算记录。")
        return

    default_idx = 0
    if st.session_state.get("last_run_id") in runs_bt["run_id"].tolist():
        default_idx = runs_bt["run_id"].tolist().index(st.session_state["last_run_id"])
    run_id = st.selectbox("选择计算批次（run）", runs_bt["run_id"].tolist(),
                          index=default_idx, key=f"run_sel_{bt}")

    meta = runs_bt[runs_bt["run_id"] == run_id].iloc[0]
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("配置名", meta["配置名"])
    r2.metric("公式版本", meta["公式版本"])
    r3.metric("样品 / 结果", f"{meta['样品数']} / {meta['结果数']}")
    r4.metric("计算时间", str(meta["计算时间"])[:19])

    wide = db.fetch_metric_pivot(run_id)
    if wide.empty:
        st.warning("该批次没有结果（可能样品已被删除）")
        return

    info_cols = ["id", "filler_type", "filler_category", "temperature_c", "c_rate",
                 "cycle_count", "initial_capacity_mah_g", "capacity_retention_pct",
                 "ionic_conductivity_ms_cm"]
    info_cols = [c for c in info_cols if c in samples.columns]
    merged = wide.merge(samples[info_cols], left_on="sample_id",
                        right_on="id", how="left").drop(columns=["id"], errors="ignore")
    rename = {c: FIELD_BY_COLUMN[c].name_cn if c in FIELD_BY_COLUMN else c
              for c in merged.columns}
    merged = merged.rename(columns=rename)
    code2cn = {m.code: m.name_cn for m in metrics.METRIC_SPECS}
    merged = merged.rename(columns=code2cn)

    st.dataframe(merged, width="stretch", hide_index=True,
                 height=min(420, 36 * len(merged) + 38))
    st.download_button(
        "⬇️ 导出结果 CSV",
        data=merged.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"metrics_{run_id}.csv", mime="text/csv")

    # 排行与分布
    score_cn = code2cn.get("composite_score")
    if score_cn and score_cn in merged.columns:
        st.markdown("##### 🏆 综合评分 Top 10")
        top = merged.dropna(subset=[score_cn]).sort_values(score_cn, ascending=False).head(10)
        show_cols = [c for c in ["填料类型", "填料类别", "初始比容量(mAh/g)",
                                 "容量保持率(%)", score_cn] if c in top.columns]
        st.dataframe(top[show_cols], width="stretch", hide_index=True)

        st.markdown("##### 📊 综合评分分布")
        st.bar_chart(top.set_index("填料类型")[score_cn]
                     if "填料类型" in top.columns else top[score_cn])

    # ---------- ⑤ 可追溯 ----------
    with st.expander("🔗 追溯：本次计算的完整参数快照"):
        run_row = db.get_connection().execute(
            "SELECT params_json, params_hash, formula_version, metric_codes,"
            " source_batch_ids, note FROM metric_runs WHERE run_id=?",
            (run_id,)).fetchone()
        if run_row:
            st.json(json.loads(run_row["params_json"]))
            st.caption(f"params_hash = `{run_row['params_hash']}`　"
                       f"formula_version = `{run_row['formula_version']}`　"
                       f"来源批次 = {run_row['source_batch_ids'] or '全部'}")

    with st.expander("🔗 追溯：单条结果的输入快照（inputs）"):
        long_df = db.fetch_metric_results(run_id)
        codes = sorted(long_df["metric_code"].unique().tolist())
        pick = st.selectbox("指标", codes, key="trace_metric")
        sub = long_df[long_df["metric_code"] == pick].head(20)
        if not sub.empty:
            rows = []
            for _, r in sub.iterrows():
                d = {"sample_id": r["sample_id"], "value": r["value"], "unit": r["unit"]}
                try:
                    d.update(json.loads(r["inputs_json"] or "{}"))
                except Exception:                 # noqa: BLE001
                    pass
                rows.append(d)
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.caption("inputs 为该指标参与计算的原始字段值，可用于手工复核口径。")

    with st.expander("🌡️ 批次级：表观活化能拟合（按材料分组，≥3 个温度点）"):
        ea = metrics.fit_activation_energy(samples)
        if ea.empty or ea["Ea_eV"].dropna().empty:
            st.info("样本温度点不足，无法拟合。导入同一材料在多个温度下的电导率后可计算。")
        else:
            st.dataframe(ea, width="stretch", hide_index=True)

    with st.expander("🗑️ 删除该计算批次"):
        if st.button("确认删除该 run", key="del_run_btn"):
            n = db.delete_metric_run(run_id)
            st.warning(f"已删除 run {run_id} 及 {n} 条结果")
            st.rerun()


# ============================================================
# Tab 9：模型版本管理（可复现 / 可回溯）
# ============================================================
def render_model_panel():
    _sub("🗂️ 模型版本管理 — 训练产物落盘 / 版本登记 / 可复现预测")
    db.init_db()

    with st.expander("① 训练并登记新版本", expanded=True):
        c1, c2, c3 = st.columns([1, 1, 1.4])
        with c1:
            bt_opt = st.radio("体系", ["液态锂硫电池", "固态锂硫电池"],
                              index=0, key="mv_bt")
            bt = LIQUID if bt_opt == "液态锂硫电池" else SOLID
        with c2:
            include_derived = st.checkbox(
                "回流指标计算（派生指标作特征/目标）", value=True, key="mv_derived",
                help="开启后把 metrics 计算结果（综合评分等）回流为额外特征/目标，"
                     "对应指标回流建模闭环（决策④）。")
        with c3:
            note = st.text_input("备注", value="", key="mv_note")
        if st.button("🚀 训练并登记版本", type="primary",
                     width="stretch", key="mv_train"):
            try:
                with st.spinner("训练中（含落盘与登记）…"):
                    vid = model_registry.train_and_register(
                        bt, include_derived=include_derived, note=note)
                st.success(f"✅ 已登记版本 {vid}（体系={'液态' if bt == LIQUID else '固态'}）")
                st.rerun()
            except Exception as e:                       # noqa: BLE001
                st.error(f"训练登记失败：{type(e).__name__}: {e}")

    st.markdown("#### ② 版本列表与激活")
    versions = model_registry.list_versions()
    if versions.empty:
        st.info("尚无登记的模型版本。在上方训练并登记第一个版本。")
    else:
        st.dataframe(versions, width="stretch", hide_index=True,
                     height=min(360, 36 * len(versions) + 38))
        sel = st.selectbox("选择版本查看详情", versions["version_id"].tolist(),
                           key="mv_sel")
        v = db.get_model_version(sel)
        if v:
            m = json.loads(v["metrics_json"] or "{}")
            st.markdown(f"**训练时间**：{v['trained_at']}　**样本数**：{v['n_samples']}　"
                        f"**公式版本**：{v['formula_version']}　"
                        f"**参数哈希**：{v['params_hash']}")
            st.caption(f"特征列：{v['feature_cols']}")
            st.caption(f"目标列：{v['target_cols']}")
            if m:
                rows = []
                for tgt, met in m.items():
                    rows.append({"目标": tgt, "最佳模型": met.get("best_model"),
                                 "R²": met.get("r2"), "MAE": met.get("mae"),
                                 "RMSE": met.get("rmse")})
                st.markdown("##### 各目标训练表现")
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            if v["is_active"]:
                st.success("✅ 当前为激活版本（预测默认使用）")
            else:
                if st.button("设为激活版本", key="mv_activate"):
                    model_registry.set_active(sel)
                    st.success(f"已将 {sel} 设为激活版本")
                    st.rerun()
