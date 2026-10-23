# -*- coding: utf-8 -*-
"""
模型版本登记与可复现模块
========================
决策③实现：模型训练产物（joblib）落盘 + 元数据入库，支持
「哪条预测由哪批数据训出」的完整回溯。

设计要点
--------
* 训练仍复用 modeling.train_models，本模块只负责：
  1) 组装训练帧（基础字段 + 可选派生指标回流，见 metrics.export_for_modeling）；
  2) 把模型三件套（results / label_encoders / scaler）序列化到 MODELS_DIR；
  3) 把训练元数据（样本数、特征/目标列、公式版本、参数哈希、来源批次、
     各目标最优 R²/MAE、产物路径）写入 db.model_versions 并登记版本号；
  4) 提供 load_version / get_active / set_active 供界面与预测加载。
* MODELS_DIR 默认在包内 models/，可用环境变量 BF_MODELS_DIR 指向包外，
  与 BF_DB_PATH 同理，避免部署覆盖丢失。
* 同体系同时只有一个 is_active=1（set_active 自动互斥）。
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import joblib

import db
import metrics
import modeling
from schema import LIQUID, SOLID

DEFAULT_MODELS_SUBDIR = "models"


def models_dir() -> str:
    env = os.environ.get("BF_MODELS_DIR")
    if env:
        os.makedirs(env, exist_ok=True)
        return env
    base = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(base, DEFAULT_MODELS_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


def build_training_frame(battery_type: str, include_derived: bool = True,
                         run_id: Optional[str] = None,
                         db_path: Optional[str] = None) -> Tuple[object, List[str], List[str]]:
    """组装训练帧。include_derived=True 时把指标计算结果作为额外特征/目标回流。"""
    if include_derived:
        return metrics.export_for_modeling(battery_type, run_id=run_id, db_path=db_path)
    import pandas as pd
    from schema import to_model_frame
    samples = db.fetch_samples(battery_type, db_path=db_path)
    if samples is None or samples.empty:
        return samples, [], []
    return to_model_frame(samples, battery_type)


def _summarize_metrics(results: dict) -> dict:
    """从 modeling.train_models 的返回里抽取各目标最优模型的 R2/MAE。"""
    summary = {}
    for target, t_res in results.items():
        best = t_res.get("best_model")
        if not best or best not in t_res:
            continue
        b = t_res[best]
        summary[target] = {
            "best_model": best,
            "r2": round(float(b.get("r2", float("nan"))), 4),
            "mae": round(float(b.get("mae", float("nan"))), 4),
            "rmse": round(float(b.get("rmse", float("nan"))), 4),
        }
    return summary


def train_and_register(battery_type: str, include_derived: bool = True,
                       source_batch_ids: Optional[List[str]] = None,
                       note: str = "", run_id: Optional[str] = None,
                       db_path: Optional[str] = None) -> str:
    """训练并登记一个模型版本，返回 version_id。"""
    db.init_db(db_path)
    frame, feats, tgts = build_training_frame(
        battery_type, include_derived=include_derived, run_id=run_id, db_path=db_path)
    if frame is None or getattr(frame, "empty", True) or len(frame) == 0:
        raise ValueError("没有可用于训练的样品数据（请先导入数据或生成内置数据）")
    if len(frame) < 6:
        raise ValueError(
            f"样本数过少（{len(frame)} 条，需 ≥6）无法训练可复现模型；"
            f"按「≥30 条纯真实样本才切真实训练」的策略，请先导入足够数据。")
    if not feats or not tgts:
        raise ValueError("特征列或目标列为空，无法训练")

    results, encoders, scaler = modeling.train_models(frame, feats, tgts)
    summary = _summarize_metrics(results)

    version_id = f"M{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    artifact_path = os.path.join(models_dir(), f"{version_id}.joblib")
    joblib.dump({
        "results": results,
        "label_encoders": encoders,
        "scaler": scaler,
        "feature_cols": feats,
        "target_cols": tgts,
        "battery_type": battery_type,
        "version_id": version_id,
    }, artifact_path)

    db.add_model_version({
        "version_id": version_id,
        "battery_type": battery_type,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "n_samples": int(len(frame)),
        "feature_cols": json.dumps(feats, ensure_ascii=False),
        "target_cols": json.dumps(tgts, ensure_ascii=False),
        "feature_spec_version": "schema-v1",
        "formula_version": metrics.METRIC_VERSION,
        "params_hash": db.compute_params_hash({"features": feats, "targets": tgts,
                                                 "include_derived": include_derived}),
        "source_batch_ids": ",".join(source_batch_ids or []),
        "metrics_json": json.dumps(summary, ensure_ascii=False),
        "artifact_path": artifact_path,
        "is_active": 1,
        "note": note or ("含派生指标回流" if include_derived else "仅基础字段"),
    }, db_path=db_path)
    return version_id


def load_version(version_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    """加载一个模型版本产物，返回 {results, label_encoders, scaler,
    feature_cols, target_cols, meta}；不存在或损坏时返回 None。"""
    meta = db.get_model_version(version_id, db_path=db_path)
    if not meta:
        return None
    path = meta.get("artifact_path")
    if not path or not os.path.exists(path):
        return None
    try:
        blob = joblib.load(path)
    except Exception:
        return None
    blob["meta"] = meta
    return blob


def list_versions(battery_type: Optional[str] = None, db_path: Optional[str] = None):
    return db.list_model_versions(battery_type=battery_type, db_path=db_path)


def get_active(battery_type: str, db_path: Optional[str] = None) -> Optional[dict]:
    return db.get_active_model_version(battery_type, db_path=db_path)


def set_active(version_id: str, db_path: Optional[str] = None) -> None:
    db.set_active_model_version(version_id, db_path=db_path)


def load_active(battery_type: str, db_path: Optional[str] = None) -> Optional[dict]:
    """加载当前激活版本；无激活版本则返回 None。"""
    v = get_active(battery_type, db_path=db_path)
    if not v:
        return None
    return load_version(v["version_id"], db_path=db_path)
