# -*- coding: utf-8 -*-
"""
数据库层（SQLite）
==================
职责：建库 / 版本化迁移 / 索引 / 表读写 / 一致性自检。

设计约束
--------
* 零外部依赖（stdlib sqlite3），Windows 云主机与 Docker 均可直接运行。
* 所有迁移幂等、按版本号顺序执行，可在旧库上安全升级。
* 写操作默认单事务：导入批次与样品行同生共死，杜绝"批次数与样品数不一致"。
* 外键强制开启（PRAGMA foreign_keys=ON），删除批次级联清理样品与计算结果。
* 结果可追溯：每个计算批次落 metric_runs（含参数快照与参数哈希），
  每条指标落 metric_results（含输入快照与公式版本）。
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from schema import (FIELD_SPECS, FIELD_BY_COLUMN, NUMERIC_COLUMNS,
                    TEXT_COLUMNS, LIQUID, SOLID)

DEFAULT_DB_NAME = "platform.db"

# 数据库路径优先级：环境变量 BF_DB_PATH > 包目录 data/platform.db
def default_db_path() -> str:
    env = os.environ.get("BF_DB_PATH")
    if env:
        return env
    base = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, DEFAULT_DB_NAME)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ============================================================
# 迁移脚本
# ============================================================
def _sql_type(spec) -> str:
    if spec.kind == "text":
        return "TEXT"
    return "INTEGER" if spec.kind == "int" else "REAL"


def _samples_columns_sql() -> str:
    lines = [
        "    id INTEGER PRIMARY KEY AUTOINCREMENT",
        "    batch_id TEXT NOT NULL REFERENCES import_batches(batch_id) ON DELETE CASCADE",
        "    battery_type TEXT NOT NULL CHECK (battery_type IN ('liquid','solid'))",
        "    content_hash TEXT NOT NULL UNIQUE",
        "    source_file TEXT",
        "    created_at TEXT NOT NULL",
        "    updated_at TEXT NOT NULL",
    ]
    lines += [f"    {s.column} {_sql_type(s)}" for s in FIELD_SPECS]
    return ",\n".join(lines)


def _samples_indexes() -> List[str]:
    idx = [
        "CREATE INDEX IF NOT EXISTS idx_samples_battery ON samples(battery_type)",
        "CREATE INDEX IF NOT EXISTS idx_samples_batch ON samples(batch_id)",
        "CREATE INDEX IF NOT EXISTS idx_samples_filler ON samples(filler_type)",
        "CREATE INDEX IF NOT EXISTS idx_samples_created ON samples(created_at)",
        # 体系 + 填料 + 工况 的常用检索组合
        "CREATE INDEX IF NOT EXISTS idx_samples_bat_filler_cond "
        "ON samples(battery_type, filler_type, temperature_c, c_rate)",
        # 性能排序/筛选
        "CREATE INDEX IF NOT EXISTS idx_samples_capacity "
        "ON samples(battery_type, initial_capacity_mah_g)",
    ]
    return idx


MIGRATIONS: List[Tuple[int, str, List[str]]] = [
    (1, "init_schema", [
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version INTEGER PRIMARY KEY,
               name TEXT NOT NULL,
               applied_at TEXT NOT NULL
           )""",
        """CREATE TABLE IF NOT EXISTS import_batches (
               batch_id TEXT PRIMARY KEY,
               source_file TEXT,
               file_md5 TEXT,
               battery_type TEXT NOT NULL,
               sheet_name TEXT,
               encoding TEXT,
               total_rows INTEGER DEFAULT 0,
               valid_rows INTEGER DEFAULT 0,
               invalid_rows INTEGER DEFAULT 0,
               duplicate_rows INTEGER DEFAULT 0,
               inserted_rows INTEGER DEFAULT 0,
               updated_rows INTEGER DEFAULT 0,
               status TEXT NOT NULL DEFAULT 'RUNNING',
               params_json TEXT,
               created_at TEXT NOT NULL,
               finished_at TEXT
           )""",
        """CREATE TABLE IF NOT EXISTS import_errors (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               batch_id TEXT NOT NULL REFERENCES import_batches(batch_id) ON DELETE CASCADE,
               row_no INTEGER NOT NULL,
               column TEXT,
               code TEXT NOT NULL,
               message TEXT NOT NULL,
               value TEXT,
               severity TEXT NOT NULL DEFAULT 'ERROR'
           )""",
        "CREATE INDEX IF NOT EXISTS idx_import_errors_batch ON import_errors(batch_id)",
        "CREATE INDEX IF NOT EXISTS idx_import_errors_code ON import_errors(code)",
        f"CREATE TABLE IF NOT EXISTS samples (\n{_samples_columns_sql()}\n)",
        """CREATE TABLE IF NOT EXISTS metric_runs (
               run_id TEXT PRIMARY KEY,
               battery_type TEXT NOT NULL,
               config_name TEXT,
               params_json TEXT NOT NULL,
               params_hash TEXT NOT NULL,
               formula_version TEXT NOT NULL,
               sample_count INTEGER DEFAULT 0,
               result_count INTEGER DEFAULT 0,
               metric_codes TEXT,
               source_batch_ids TEXT,
               note TEXT,
               created_at TEXT NOT NULL
           )""",
        "CREATE INDEX IF NOT EXISTS idx_metric_runs_battery ON metric_runs(battery_type)",
        "CREATE INDEX IF NOT EXISTS idx_metric_runs_time ON metric_runs(created_at)",
        """CREATE TABLE IF NOT EXISTS metric_results (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               run_id TEXT NOT NULL REFERENCES metric_runs(run_id) ON DELETE CASCADE,
               sample_id INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
               metric_code TEXT NOT NULL,
               value REAL,
               unit TEXT,
               precision INTEGER DEFAULT 4,
               formula_version TEXT NOT NULL,
               params_hash TEXT NOT NULL,
               inputs_json TEXT,
               computed_at TEXT NOT NULL
           )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_metric_result "
        "ON metric_results(run_id, sample_id, metric_code)",
        "CREATE INDEX IF NOT EXISTS idx_metric_results_run "
        "ON metric_results(run_id, metric_code)",
        "CREATE INDEX IF NOT EXISTS idx_metric_results_sample ON metric_results(sample_id)",
        "CREATE INDEX IF NOT EXISTS idx_metric_results_value "
        "ON metric_results(metric_code, value)",
    ] + _samples_indexes()),
    # 说明：这里刻意用普通索引而非唯一索引——同一文件允许按不同去重策略重复导入，
    # 重复拦截交给 content_hash（行级）处理；该索引只用于"这个文件导入过几次"的查询。
    (2, "add_batch_file_index", [
        "CREATE INDEX IF NOT EXISTS idx_batch_file_md5 "
        "ON import_batches(file_md5, battery_type)",
    ]),
    # v3：① 给导入批次加可查询的「数据来源」列；② 新增模型版本登记表（可复现/回溯）
    (3, "add_source_tag_and_model_versions", [
        "ALTER TABLE import_batches ADD COLUMN source_tag TEXT",
        """CREATE TABLE IF NOT EXISTS model_versions (
               version_id TEXT PRIMARY KEY,
               battery_type TEXT NOT NULL,
               trained_at TEXT NOT NULL,
               n_samples INTEGER DEFAULT 0,
               feature_cols TEXT NOT NULL,
               target_cols TEXT NOT NULL,
               feature_spec_version TEXT,
               formula_version TEXT,
               params_hash TEXT,
               source_batch_ids TEXT,
               metrics_json TEXT,
               artifact_path TEXT,
               is_active INTEGER DEFAULT 0,
               note TEXT
           )""",
        "CREATE INDEX IF NOT EXISTS idx_model_versions_battery "
        "ON model_versions(battery_type)",
        "CREATE INDEX IF NOT EXISTS idx_model_versions_active "
        "ON model_versions(battery_type, is_active)",
    ]),
]


# ============================================================
# 连接管理
# ============================================================
_local = threading.local()


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """获取线程内复用连接（SQLite 连接非线程安全，Streamlit 多线程必须用 thread-local）。"""
    path = db_path or default_db_path()
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != path:
        conn = sqlite3.connect(path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        _local.conn = conn
        _local.path = path
        conn.execute  # noqa
    return conn


@contextmanager
def transaction(db_path: Optional[str] = None):
    """事务上下文：成功提交，异常整体回滚。"""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db(db_path: Optional[str] = None) -> List[int]:
    """执行未应用的迁移，返回本次新应用的版本号列表。"""
    conn = get_connection(db_path)
    applied: List[int] = []
    with transaction(db_path):
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)")
        done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        for version, name, stmts in MIGRATIONS:
            if version in done:
                continue
            for sql in stmts:
                conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?,?,?)",
                (version, name, now_iso()))
            applied.append(version)
    return applied


def db_version(db_path: Optional[str] = None) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
        return int(row["v"] or 0)
    except sqlite3.Error:
        return 0


# ============================================================
# 工具
# ============================================================
def compute_content_hash(record: dict, battery_type: str) -> str:
    """内容哈希：材料+结构+工况+性能 全字段归一化后取 SHA-256（取前 32 位）。

    归一化规则：文本去空白统一大小写；数值按字段精度四舍五入，
    消除 1.20000001 / 1.2 这类浮点尾差造成的假重复。
    """
    parts = [battery_type]
    for spec in FIELD_SPECS:
        v = record.get(spec.column)
        if v is None:
            parts.append("")
        elif spec.kind == "text":
            parts.append(str(v).strip().lower())
        elif spec.kind == "int":
            parts.append(str(int(v)))
        else:
            parts.append(f"{round(float(v), spec.precision):.{spec.precision}f}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def compute_params_hash(params: dict) -> str:
    blob = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def file_md5(path_or_bytes) -> str:
    h = hashlib.md5()
    if isinstance(path_or_bytes, (bytes, bytearray)):
        h.update(path_or_bytes)
    else:
        with open(path_or_bytes, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()


# ============================================================
# 批次与样品写入
# ============================================================
def create_batch(meta: dict, db_path: Optional[str] = None) -> str:
    conn = get_connection(db_path)
    cols = ["batch_id", "source_file", "file_md5", "battery_type", "sheet_name",
            "encoding", "total_rows", "status", "params_json", "created_at",
            "source_tag"]
    row = {k: meta.get(k) for k in cols}
    row["status"] = row.get("status") or "RUNNING"
    row["created_at"] = row.get("created_at") or now_iso()
    # source_tag 优先取顶层；否则从 params 中解析（与 importer 写入方式兼容）
    if not row.get("source_tag"):
        row["source_tag"] = (meta.get("params") or {}).get("source_tag", "")
    row["params_json"] = json.dumps(meta.get("params", {}), ensure_ascii=False)
    placeholders = ",".join("?" for _ in cols)
    with transaction(db_path):
        conn.execute(
            f"INSERT OR REPLACE INTO import_batches ({','.join(cols)}) VALUES ({placeholders})",
            [row[c] for c in cols])
    return row["batch_id"]


def finish_batch(batch_id: str, stats: dict, status: str = "SUCCESS",
                 db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    allowed = {"total_rows", "valid_rows", "invalid_rows", "duplicate_rows",
               "inserted_rows", "updated_rows"}
    sets = ", ".join(f"{k}=?" for k in stats if k in allowed)
    vals = [stats[k] for k in stats if k in allowed]
    with transaction(db_path):
        conn.execute(
            f"UPDATE import_batches SET {sets}, status=?, finished_at=? WHERE batch_id=?",
            vals + [status, now_iso(), batch_id])


def insert_samples(records: Sequence[dict], batch_id: str, battery_type: str,
                   dedupe: str = "skip", db_path: Optional[str] = None) -> dict:
    """批量写入样品。

    dedupe: skip（忽略重复）| update（覆盖已有行的字段）
    返回 {'inserted': n, 'updated': n, 'duplicated': n}
    """
    conn = get_connection(db_path)
    cols = ["batch_id", "battery_type", "content_hash", "source_file",
            "created_at", "updated_at"] + [s.column for s in FIELD_SPECS]
    sql = ("INSERT INTO samples (" + ",".join(cols) + ") VALUES (" +
           ",".join("?" for _ in cols) + ")")
    stats = {"inserted": 0, "updated": 0, "duplicated": 0}
    # 注意：覆盖更新时不变更 batch_id —— 样品归属"首次导入批次"，
    # 这样 import_batches.inserted_rows 与实际行数始终对得上（一致性校验依赖此约定）。
    upd_cols = [s.column for s in FIELD_SPECS] + ["updated_at"]
    upd_sql = ("UPDATE samples SET " + ", ".join(f"{c}=?" for c in upd_cols) +
               " WHERE content_hash=?")

    with transaction(db_path):
        for rec in records:
            ch = rec["content_hash"]
            full = dict(rec)
            full["batch_id"] = batch_id
            full["battery_type"] = battery_type
            full["source_file"] = rec.get("source_file") or ""
            ts = now_iso()
            full["created_at"] = rec.get("created_at") or ts
            full["updated_at"] = ts
            exists = conn.execute(
                "SELECT id FROM samples WHERE content_hash=?", (ch,)).fetchone()
            if exists and dedupe == "skip":
                stats["duplicated"] += 1
                continue
            if exists:
                conn.execute(upd_sql, [full.get(c) for c in upd_cols] + [ch])
                stats["updated"] += 1
                continue
            conn.execute(sql, [full.get(c) for c in cols])
            stats["inserted"] += 1
    return stats


def insert_errors(errors: Sequence[dict], db_path: Optional[str] = None) -> int:
    if not errors:
        return 0
    conn = get_connection(db_path)
    cols = ["batch_id", "row_no", "column", "code", "message", "value", "severity"]
    sql = f"INSERT INTO import_errors ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})"
    with transaction(db_path):
        conn.executemany(sql, [[e.get(c) for c in cols] for e in errors])
    return len(errors)


# ============================================================
# 查询
# ============================================================
def fetch_samples(battery_type: Optional[str] = None, batch_id: Optional[str] = None,
                  limit: Optional[int] = None, db_path: Optional[str] = None):
    import pandas as pd
    conn = get_connection(db_path)
    where, args = [], []
    if battery_type:
        where.append("battery_type=?")
        args.append(battery_type)
    if batch_id:
        where.append("batch_id=?")
        args.append(batch_id)
    sql = "SELECT * FROM samples"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql, args).fetchall()
    cols = ["id", "batch_id", "battery_type", "content_hash", "source_file",
            "created_at", "updated_at"] + [s.column for s in FIELD_SPECS]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame([tuple(r[c] for c in cols) for r in rows], columns=cols)


def list_batches(db_path: Optional[str] = None, limit: int = 50):
    import pandas as pd
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT batch_id, source_file, battery_type, sheet_name, total_rows, valid_rows,"
        " invalid_rows, duplicate_rows, inserted_rows, updated_rows, status,"
        " source_tag, created_at, finished_at FROM import_batches"
        " ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return pd.DataFrame([tuple(r) for r in rows],
                        columns=["batch_id", "源文件", "体系", "工作表", "总行数", "有效行",
                                 "错误行", "重复行", "新增", "更新", "状态", "来源",
                                 "开始时间", "完成时间"]) if rows else pd.DataFrame()


def find_batches_by_source(source_tag: str, db_path: Optional[str] = None) -> List[dict]:
    """按数据来源标签查询导入批次（支持按来源筛选/统计）。"""
    if not source_tag:
        return []
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT batch_id, source_file, battery_type, inserted_rows, created_at"
        " FROM import_batches WHERE source_tag=? ORDER BY created_at DESC",
        (source_tag,)).fetchall()
    return [dict(r) for r in rows]


def fetch_errors(batch_id: str, severity: Optional[str] = None, limit: int = 500,
                 db_path: Optional[str] = None):
    import pandas as pd
    conn = get_connection(db_path)
    sql = ("SELECT row_no, column, code, message, value, severity FROM import_errors"
           " WHERE batch_id=?")
    args = [batch_id]
    if severity:
        sql += " AND severity=?"
        args.append(severity)
    sql += " ORDER BY row_no, id LIMIT ?"
    args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    return pd.DataFrame([tuple(r) for r in rows],
                        columns=["行号", "字段", "错误码", "说明", "原始值", "级别"]) if rows else pd.DataFrame()


def find_batches_by_md5(md5: str, db_path: Optional[str] = None) -> List[dict]:
    """按文件 MD5 查询历史导入批次（用于提示"该文件可能已导入过"）。"""
    if not md5:
        return []
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT batch_id, source_file, battery_type, inserted_rows, created_at"
        " FROM import_batches WHERE file_md5=? ORDER BY created_at DESC",
        (md5,)).fetchall()
    return [dict(r) for r in rows]


def delete_batch(batch_id: str, db_path: Optional[str] = None) -> dict:
    """删除批次及其样品、计算级联结果（外键 ON DELETE CASCADE）。"""
    conn = get_connection(db_path)
    with transaction(db_path):
        n_res = conn.execute(
            "SELECT COUNT(*) FROM metric_results WHERE sample_id IN "
            "(SELECT id FROM samples WHERE batch_id=?)", (batch_id,)).fetchone()[0]
        conn.execute("DELETE FROM samples WHERE batch_id=?", (batch_id,))
        conn.execute("DELETE FROM import_errors WHERE batch_id=?", (batch_id,))
        conn.execute("DELETE FROM import_batches WHERE batch_id=?", (batch_id,))
        # 样品被级联删除后，同步重算受影响计算批次的 result_count，
        # 否则 metric_runs.result_count 会大于 metric_results 实际条数。
        conn.execute(
            "UPDATE metric_runs SET result_count = ("
            "  SELECT COUNT(*) FROM metric_results r"
            "  WHERE r.run_id = metric_runs.run_id)")
    return {"deleted_batch": batch_id, "deleted_metric_results": n_res}


def sync_run_counts(db_path: Optional[str] = None) -> int:
    """把所有 metric_runs.result_count 对齐为实际结果条数，返回受影响的 run 数。"""
    conn = get_connection(db_path)
    with transaction(db_path):
        cur = conn.execute(
            "UPDATE metric_runs SET result_count = ("
            "  SELECT COUNT(*) FROM metric_results r"
            "  WHERE r.run_id = metric_runs.run_id)"
            " WHERE result_count <> ("
            "  SELECT COUNT(*) FROM metric_results r2"
            "  WHERE r2.run_id = metric_runs.run_id)")
        return cur.rowcount or 0


# ============================================================
# 计算结果读写
# ============================================================
def create_metric_run(run: dict, db_path: Optional[str] = None) -> str:
    conn = get_connection(db_path)
    cols = ["run_id", "battery_type", "config_name", "params_json", "params_hash",
            "formula_version", "sample_count", "result_count", "metric_codes",
            "source_batch_ids", "note", "created_at"]
    row = {k: run.get(k) for k in cols}
    row["created_at"] = row.get("created_at") or now_iso()
    row["params_json"] = row.get("params_json") or "{}"
    with transaction(db_path):
        conn.execute(
            f"INSERT OR REPLACE INTO metric_runs ({','.join(cols)}) VALUES "
            f"({','.join('?' for _ in cols)})", [row[c] for c in cols])
    return row["run_id"]


def save_metric_results(results: Sequence[dict], db_path: Optional[str] = None) -> int:
    if not results:
        return 0
    conn = get_connection(db_path)
    cols = ["run_id", "sample_id", "metric_code", "value", "unit", "precision",
            "formula_version", "params_hash", "inputs_json", "computed_at"]
    sql = ("INSERT OR REPLACE INTO metric_results (" + ",".join(cols) + ") VALUES (" +
           ",".join("?" for _ in cols) + ")")
    with transaction(db_path):
        conn.executemany(sql, [[r.get(c) for c in cols] for r in results])
    return len(results)


def fetch_metric_results(run_id: str, db_path: Optional[str] = None):
    """取某次计算的全量结果（长表：sample_id × metric_code）。"""
    import pandas as pd
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT sample_id, metric_code, value, unit, precision, inputs_json"
        " FROM metric_results WHERE run_id=?", (run_id,)).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([tuple(r) for r in rows],
                        columns=["sample_id", "metric_code", "value", "unit",
                                 "precision", "inputs_json"])


def fetch_metric_pivot(run_id: str, db_path: Optional[str] = None):
    """宽表形式：一行一样品，一列一指标。"""
    long = fetch_metric_results(run_id, db_path)
    if long.empty:
        return long
    return long.pivot(index="sample_id", columns="metric_code", values="value").reset_index()


def list_metric_runs(db_path: Optional[str] = None, limit: int = 50):
    import pandas as pd
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT run_id, battery_type, config_name, formula_version, params_hash,"
        " sample_count, result_count, created_at, note FROM metric_runs"
        " ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return pd.DataFrame([tuple(r) for r in rows],
                        columns=["run_id", "体系", "配置名", "公式版本", "参数哈希",
                                 "样品数", "结果数", "计算时间", "备注"]) if rows else pd.DataFrame()


def delete_metric_run(run_id: str, db_path: Optional[str] = None) -> int:
    conn = get_connection(db_path)
    with transaction(db_path):
        n = conn.execute("SELECT COUNT(*) FROM metric_results WHERE run_id=?",
                         (run_id,)).fetchone()[0]
        conn.execute("DELETE FROM metric_results WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM metric_runs WHERE run_id=?", (run_id,))
    return n


# ============================================================
# 一致性自检
# ============================================================
def verify_consistency(db_path: Optional[str] = None) -> List[dict]:
    """对导入、计算、存储三环节做交叉校验，返回检查项列表。

    每项: {'check', 'status': OK/FAIL, 'detail', 'count'}
    """
    conn = get_connection(db_path)
    checks: List[dict] = []

    def add(name, ok, detail, count=0):
        checks.append({"check": name, "status": "OK" if ok else "FAIL",
                       "detail": detail, "count": count})

    # 1. 样品无重复内容哈希（UNIQUE 索引兜底，这里做一次显式扫描）
    dup = conn.execute(
        "SELECT content_hash, COUNT(*) n FROM samples GROUP BY content_hash"
        " HAVING n > 1").fetchall()
    add("样品内容哈希唯一", not dup, f"重复哈希 {len(dup)} 组", len(dup))

    # 2. 批次统计与样品实际行数一致
    mism = conn.execute(
        "SELECT b.batch_id, b.inserted_rows AS declared,"
        " (SELECT COUNT(*) FROM samples s WHERE s.batch_id=b.batch_id) AS actual"
        " FROM import_batches b WHERE b.status='SUCCESS'"
        " AND declared <> actual").fetchall()
    add("批次统计=实际行数", not mism,
        "；".join(f"{r[0]}: 记录{r[1]}/实际{r[2]}" for r in mism[:5]), len(mism))

    # 3. 计算结果无孤儿（sample_id 必须存在）
    orphan = conn.execute(
        "SELECT COUNT(*) FROM metric_results r LEFT JOIN samples s"
        " ON r.sample_id=s.id WHERE s.id IS NULL").fetchone()[0]
    add("计算结果无孤儿记录", orphan == 0, f"孤儿 {orphan} 条", orphan)

    # 4. 计算批次 result_count 与实际一致
    rc = conn.execute(
        "SELECT m.run_id, m.result_count, (SELECT COUNT(*) FROM metric_results r"
        " WHERE r.run_id=m.run_id) AS actual FROM metric_runs m"
        " WHERE m.result_count <> actual").fetchall()
    add("计算批次计数一致", not rc,
        "；".join(f"{r[0]}: 记录{r[1]}/实际{r[2]}" for r in rc[:5]), len(rc))

    # 5. 同一 run 内 参数哈希一致（防止部分写入时参数被改动）
    ph = conn.execute(
        "SELECT run_id, COUNT(DISTINCT params_hash) k FROM metric_results"
        " GROUP BY run_id HAVING k > 1").fetchall()
    add("批次内参数哈希一致", not ph,
        "；".join(r[0] for r in ph[:5]), len(ph))

    # 6. 必填字段非空
    conds = " OR ".join(f"{s.column} IS NULL" for s in FIELD_SPECS if s.required)
    if conds:
        miss = conn.execute(f"SELECT COUNT(*) FROM samples WHERE {conds}").fetchone()[0]
        add("必填字段非空", miss == 0, f"缺失 {miss} 行", miss)

    # 7. 外键完整性
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    add("外键完整性", not fk, f"违规 {len(fk)} 条", len(fk))

    return checks


def db_summary(db_path: Optional[str] = None) -> dict:
    conn = get_connection(db_path)
    def one(sql, args=()):
        return conn.execute(sql, args).fetchone()[0]
    return {
        "db_path": db_path or default_db_path(),
        "schema_version": db_version(db_path),
        "samples": one("SELECT COUNT(*) FROM samples"),
        "liquid": one("SELECT COUNT(*) FROM samples WHERE battery_type=?", (LIQUID,)),
        "solid": one("SELECT COUNT(*) FROM samples WHERE battery_type=?", (SOLID,)),
        "batches": one("SELECT COUNT(*) FROM import_batches"),
        "metric_runs": one("SELECT COUNT(*) FROM metric_runs"),
        "metric_results": one("SELECT COUNT(*) FROM metric_results"),
        "errors": one("SELECT COUNT(*) FROM import_errors"),
    }


# ============================================================
# 模型版本（可复现 / 可回溯）
# ============================================================
def add_model_version(v: dict, db_path: Optional[str] = None) -> str:
    """登记一个模型版本。v 键：version_id, battery_type, trained_at, n_samples,
    feature_cols, target_cols, feature_spec_version, formula_version, params_hash,
    source_batch_ids, metrics_json, artifact_path, note。
    写入时会先把同体系其它版本 is_active 清零（若本版本 is_active=1）。"""
    conn = get_connection(db_path)
    cols = ["version_id", "battery_type", "trained_at", "n_samples",
            "feature_cols", "target_cols", "feature_spec_version",
            "formula_version", "params_hash", "source_batch_ids",
            "metrics_json", "artifact_path", "is_active", "note"]
    row = {k: v.get(k) for k in cols}
    row["is_active"] = 1 if v.get("is_active") else 0
    with transaction(db_path):
        if row["is_active"]:
            conn.execute(
                "UPDATE model_versions SET is_active=0 WHERE battery_type=?",
                (row["battery_type"],))
        conn.execute(
            f"INSERT OR REPLACE INTO model_versions ({','.join(cols)}) VALUES "
            f"({','.join('?' for _ in cols)})", [row[c] for c in cols])
    return row["version_id"]


def list_model_versions(battery_type: Optional[str] = None,
                         db_path: Optional[str] = None) -> "pd.DataFrame":
    import pandas as pd
    conn = get_connection(db_path)
    sql = ("SELECT version_id, battery_type, trained_at, n_samples, formula_version,"
           " params_hash, source_batch_ids, metrics_json, artifact_path, is_active, note"
           " FROM model_versions")
    args = []
    if battery_type:
        sql += " WHERE battery_type=?"
        args.append(battery_type)
    sql += " ORDER BY trained_at DESC"
    rows = conn.execute(sql, args).fetchall()
    return pd.DataFrame([tuple(r) for r in rows],
                        columns=["version_id", "体系", "训练时间", "样本数",
                                 "公式版本", "参数哈希", "来源批次", "指标摘要",
                                 "产物路径", "是否激活", "备注"]) if rows else pd.DataFrame()


def get_model_version(version_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM model_versions WHERE version_id=?", (version_id,)).fetchone()
    return dict(row) if row else None


def get_active_model_version(battery_type: str, db_path: Optional[str] = None) -> Optional[dict]:
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM model_versions WHERE battery_type=? AND is_active=1"
        " ORDER BY trained_at DESC LIMIT 1", (battery_type,)).fetchone()
    return dict(row) if row else None


def set_active_model_version(version_id: str, db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    v = get_model_version(version_id, db_path)
    if not v:
        raise ValueError(f"未知的模型版本：{version_id}")
    with transaction(db_path):
        conn.execute(
            "UPDATE model_versions SET is_active=0 WHERE battery_type=?",
            (v["battery_type"],))
        conn.execute(
            "UPDATE model_versions SET is_active=1 WHERE version_id=?",
            (version_id,))
