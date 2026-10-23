# -*- coding: utf-8 -*-
"""
批量文件导入引擎
================
支持 CSV / TSV / TXT / Excel(xlsx, xlsm, xls) 的解析、字段校验、去重、进度反馈与落库。

处理流水线
----------
读取(编码/分隔符/表头探测) → 列映射 → 体系判定 → 逐行校验(ERROR/WARN)
→ 内容哈希去重(批内+库内) → 事务落库(批次+样品+错误) → 结果汇总

约束
----
* 行级原子性：单条记录校验失败只丢弃该行，不影响整批（错误明细入库可回溯）。
* 批次级原子性：批次头、样品行、错误明细在同一事务提交，计数字段与实际行数一致。
* 幂等：同一文件（MD5 + 体系 + 工作表）重复导入时，重复行按 dedupe 策略处理，
  不会产生重复样品（content_hash UNIQUE 兜底）。
"""
from __future__ import annotations

import io
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

import pandas as pd

import db
from schema import (FIELD_SPECS, FIELD_BY_COLUMN, BATTERY_TYPES, LIQUID, SOLID,
                    BATTERY_TYPE_CN, ValidationIssue, coerce_value,
                    cross_field_checks, detect_battery_type, map_columns,
                    normalize_header)

SUPPORTED_EXT = {".csv", ".txt", ".tsv", ".xlsx", ".xlsm", ".xls"}
CANDIDATE_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "latin1")
MAX_ERROR_ROWS_STORED = 2000          # 单批次最多入库的错误明细条数
PREVIEW_ROWS = 5                      # 表头探测扫描行数


# ============================================================
# 配置与结果
# ============================================================
@dataclass
class ImportConfig:
    battery_type: str = "auto"        # auto | liquid | solid
    dedupe: str = "skip"              # skip | update
    sheet_name: Optional[str] = None  # Excel 工作表名，None=第一个
    header_row: Optional[int] = None  # 0-based，None=自动探测
    encoding: Optional[str] = None    # None=自动探测
    delimiter: Optional[str] = None   # None=自动探测
    strict_mode: bool = False         # True：存在任一 ERROR 行则整批回滚
    source_tag: str = ""              # 数据来源标注（文献/课题组/设备导出）

    def validate(self) -> None:
        if self.battery_type not in ("auto",) + BATTERY_TYPES:
            raise ValueError(f"battery_type 非法: {self.battery_type}")
        if self.dedupe not in ("skip", "update"):
            raise ValueError(f"dedupe 非法: {self.dedupe}")


@dataclass
class ImportReport:
    batch_id: str = ""
    source_file: str = ""
    battery_type: str = ""
    sheet_name: str = ""
    encoding: str = ""
    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    duplicate_rows: int = 0
    inserted_rows: int = 0
    updated_rows: int = 0
    status: str = "PENDING"           # SUCCESS | FAILED | ROLLBACK | PENDING
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    missing_columns: List[str] = field(default_factory=list)
    unmapped_columns: List[str] = field(default_factory=list)
    message: str = ""
    elapsed_ms: int = 0

    def as_dict(self) -> dict:
        d = asdict(self)
        d["errors"] = [e.as_dict() for e in self.errors]
        d["warnings"] = [e.as_dict() for e in self.warnings]
        return d

    def summary_lines(self) -> List[str]:
        return [
            f"批次号：{self.batch_id}",
            f"体系：{BATTERY_TYPE_CN.get(self.battery_type, self.battery_type)}",
            f"总行数：{self.total_rows}｜有效：{self.valid_rows}｜"
            f"错误：{self.invalid_rows}｜重复：{self.duplicate_rows}",
            f"新增：{self.inserted_rows}｜更新：{self.updated_rows}｜"
            f"状态：{self.status}",
        ]


ProgressCB = Callable[[str, float, str], None]


def _noop_progress(stage: str, pct: float, detail: str) -> None:
    return None


# ============================================================
# 1. 读取
# ============================================================
def _sniff_delimiter(sample: str) -> str:
    for d in (",", "\t", ";", "|"):
        if sample.count(d) >= 1:
            # 简单投票：取首行出现次数最多的候选
            first = sample.splitlines()[0] if sample else ""
            counts = {c: first.count(c) for c in (",", "\t", ";", "|")}
            best = max(counts, key=lambda k: counts[k])
            return best if counts[best] > 0 else d
    return ","


def read_raw(file_obj: Union[str, bytes, io.BytesIO], filename: str,
             config: ImportConfig) -> Tuple[pd.DataFrame, dict]:
    """读取文件为 DataFrame（不做列映射）。返回 (df, meta)。"""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXT:
        raise ValueError(f"不支持的文件类型：{ext}（支持 {sorted(SUPPORTED_EXT)}）")

    meta = {"ext": ext, "encoding": config.encoding or "", "sheet_name": ""}

    if ext in (".xlsx", ".xlsm", ".xls"):
        engine = "openpyxl" if ext in (".xlsx", ".xlsm") else "xlrd"
        try:
            book = pd.ExcelFile(file_obj, engine=engine)
        except ImportError as e:
            raise ImportError(f"读取 {ext} 需要安装 {engine}：pip install {engine}") from e
        sheets = book.sheet_names
        sheet = config.sheet_name if config.sheet_name in sheets else sheets[0]
        meta["sheet_name"] = sheet
        meta["sheets"] = sheets
        df = pd.read_excel(book, sheet_name=sheet, header=None, dtype=object)
        meta["encoding"] = "excel"
    else:
        if isinstance(file_obj, (bytes, bytearray)):
            raw = bytes(file_obj)
        elif hasattr(file_obj, "getvalue"):
            raw = file_obj.getvalue()      # streamlit UploadedFile 直接传入
            if not isinstance(raw, (bytes, bytearray)):
                raw = raw.encode("utf-8", errors="replace") if isinstance(raw, str) \
                    else bytes(raw)
        elif hasattr(file_obj, "read"):
            raw = file_obj.read()
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
        else:
            with open(file_obj, "rb") as f:
                raw = f.read()

        enc = config.encoding
        if not enc:
            enc = None
            for cand in CANDIDATE_ENCODINGS:
                try:
                    raw.decode(cand)
                    enc = cand
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            enc = enc or "utf-8"
        meta["encoding"] = enc
        text = raw.decode(enc, errors="replace")
        delim = config.delimiter or _sniff_delimiter(text[:4096])
        meta["delimiter"] = delim
        df = pd.read_csv(io.StringIO(text), sep=delim, header=None, dtype=object,
                         skip_blank_lines=True)

    df = df.dropna(how="all")
    df = df.reset_index(drop=True)
    return df, meta


def detect_header_row(df: pd.DataFrame, sample: int = PREVIEW_ROWS) -> int:
    """在前 sample 行中，选择"可识别字段最多"的一行作为表头。"""
    best_row, best_score = 0, -1
    for i in range(min(sample, len(df))):
        headers = [str(x) for x in df.iloc[i].tolist() if pd.notna(x)]
        _, unknown = map_columns(headers)
        score = len(headers) - len(unknown)
        if score > best_score:
            best_row, best_score = i, score
    return best_row


def apply_header(df: pd.DataFrame, header_row: int) -> pd.DataFrame:
    header = [("" if pd.isna(x) else str(x).strip()) for x in df.iloc[header_row].tolist()]
    body = df.iloc[header_row + 1:].copy()
    body.columns = [h if h else f"__col_{i}" for i, h in enumerate(header)]
    return body.reset_index(drop=True)


# ============================================================
# 2. 解析为标准化记录（不落库，可用于预览）
# ============================================================
def parse_records(df_raw: pd.DataFrame, config: ImportConfig,
                  progress: ProgressCB = _noop_progress
                  ) -> Tuple[List[dict], List[ValidationIssue], List[ValidationIssue],
                             List[str], List[str], str, str]:
    """逐行校验并生成标准记录。

    返回 (records, errors, warnings, missing_columns, unmapped_columns, battery_type, sheet)
    """
    header_row = config.header_row if config.header_row is not None \
        else detect_header_row(df_raw)
    body = apply_header(df_raw, header_row)
    if body.empty:
        return [], [], [], [], [], "", ""

    mapping, unmapped = map_columns(list(body.columns))
    if not mapping:
        raise ValueError(
            "未能识别任何标准字段。请检查表头是否为平台模板列名"
            "（可在导入页下载模板对照）。")

    # 体系判定
    btype = config.battery_type
    if btype == "auto":
        btype = detect_battery_type(list(mapping.values())) or \
            detect_battery_type(list(body.columns)) or LIQUID

    # 必填/适用字段检查
    applicable = [s for s in FIELD_SPECS if btype in s.applies_to]
    mapped_cols = set(mapping.values())
    missing = [s.name_cn for s in applicable if s.required and s.column not in mapped_cols]

    total = len(body)
    records: List[dict] = []
    errors: List[ValidationIssue] = []
    warnings: List[ValidationIssue] = []
    seen_hash: Dict[str, int] = {}

    for offset, (_, row) in enumerate(body.iterrows()):
        row_no = offset + 1                      # 相对数据区的 1-based 行号
        abs_row_no = header_row + 2 + offset     # 文件中的绝对行号，便于回溯
        rec: dict = {}
        row_errors: List[ValidationIssue] = []
        row_warnings: List[ValidationIssue] = []

        for orig_col, std_col in mapping.items():
            spec = FIELD_BY_COLUMN[std_col]
            if btype not in spec.applies_to:
                continue                          # 非本体系字段直接忽略
            val, iss = coerce_value(spec, row.get(orig_col), abs_row_no)
            rec[std_col] = val
            for i in iss:
                (row_errors if i.severity == "ERROR" else row_warnings).append(i)

        if row_errors:
            errors.extend(row_errors)
            errors.extend(row_warnings)
            if (offset + 1) % 200 == 0:
                progress("validate", 30 + 45 * (offset + 1) / max(total, 1),
                         f"已校验 {offset + 1}/{total} 行")
            continue

        warnings.extend(row_warnings)
        warnings.extend(cross_field_checks(rec, btype, abs_row_no))

        ch = db.compute_content_hash(rec, btype)
        if ch in seen_hash:
            errors.append(ValidationIssue(
                abs_row_no, "*", "DUPLICATE_IN_FILE",
                f"与文件内第 {seen_hash[ch]} 行数据完全重复，已跳过", None, "ERROR"))
            continue
        seen_hash[ch] = row_no

        rec["content_hash"] = ch
        rec["battery_type"] = btype
        records.append(rec)

        if (offset + 1) % 200 == 0:
            progress("validate", 30 + 45 * (offset + 1) / max(total, 1),
                     f"已校验 {offset + 1}/{total} 行")

    progress("validate", 75.0, f"校验完成：有效 {len(records)} / 共 {total}")
    return records, errors, warnings, missing, unmapped, btype, ""


# ============================================================
# 3. 完整导入（解析 + 落库）
# ============================================================
def import_file(file_obj: Union[str, bytes, io.BytesIO], filename: str,
                config: Optional[ImportConfig] = None,
                db_path: Optional[str] = None,
                progress: ProgressCB = _noop_progress) -> ImportReport:
    """导入一个文件。返回 ImportReport。"""
    started = datetime.now()
    config = config or ImportConfig()
    config.validate()
    db.init_db(db_path)

    report = ImportReport(source_file=os.path.basename(filename))

    # ---- 读取 ----
    progress("read", 5, f"读取文件 {os.path.basename(filename)}")
    df_raw, meta = read_raw(file_obj, filename, config)
    report.encoding = meta.get("encoding", "")
    report.sheet_name = meta.get("sheet_name", "")
    progress("read", 20, f"共读取 {len(df_raw)} 行")

    # ---- 解析校验 ----
    progress("map", 25, "识别列映射与电池体系")
    records, errors, warnings, missing, unmapped, btype, _ = parse_records(
        df_raw, config, progress)
    report.battery_type = btype
    report.missing_columns = missing
    report.unmapped_columns = unmapped
    report.errors = errors
    report.warnings = warnings

    if missing:
        report.status = "FAILED"
        report.message = f"缺少必填列：{missing}"
        progress("done", 100, report.message)
        report.elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
        return report

    header_row_for_count = (config.header_row if config.header_row is not None
                             else detect_header_row(df_raw))
    total_rows = len(df_raw) - (header_row_for_count + 1)
    dup_in_file = sum(1 for e in errors if e.code == "DUPLICATE_IN_FILE")
    report.total_rows = max(total_rows, 0)
    report.valid_rows = len(records)
    report.invalid_rows = max(report.total_rows - len(records) - dup_in_file, 0)

    if not records:
        report.status = "FAILED"
        report.message = "没有可导入的有效数据行，请查看错误明细"
        progress("done", 100, report.message)
        report.elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
        return report

    if config.strict_mode and errors:
        report.status = "ROLLBACK"
        report.message = f"严格模式：存在 {len(errors)} 条错误，整批未写入"
        progress("done", 100, report.message)
        report.elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
        return report

    # ---- 落库 ----
    progress("persist", 82, f"写入数据库（{len(records)} 条）")
    batch_id = f"B{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    try:
        if isinstance(file_obj, (str, bytes, bytearray)):
            raw_for_md5 = file_obj
        elif hasattr(file_obj, "getvalue"):        # streamlit UploadedFile
            raw_for_md5 = file_obj.getvalue()
        elif hasattr(file_obj, "read"):
            raw_for_md5 = file_obj.read()
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
        else:
            raw_for_md5 = file_obj
        md5 = db.file_md5(raw_for_md5)
    except Exception:
        md5 = ""

    db.create_batch({
        "batch_id": batch_id,
        "source_file": report.source_file,
        "file_md5": md5 or f"mem-{uuid.uuid4().hex[:12]}",
        "battery_type": btype,
        "sheet_name": report.sheet_name,
        "encoding": report.encoding,
        "total_rows": report.total_rows,
        "params": asdict(config) | {"source_tag": config.source_tag},
    }, db_path=db_path)

    db.insert_errors([e.as_dict() | {"batch_id": batch_id}
                      for e in (errors + warnings)[:MAX_ERROR_ROWS_STORED]],
                     db_path=db_path)

    stats = db.insert_samples(records, batch_id, btype, config.dedupe, db_path=db_path)
    report.duplicate_rows = dup_in_file + stats["duplicated"]
    report.inserted_rows = stats["inserted"]
    report.updated_rows = stats["updated"]

    db.finish_batch(batch_id, {
        "total_rows": report.total_rows,
        "valid_rows": report.valid_rows,
        "invalid_rows": report.invalid_rows,
        "duplicate_rows": report.duplicate_rows,
        "inserted_rows": report.inserted_rows,
        "updated_rows": report.updated_rows,
    }, status="SUCCESS", db_path=db_path)

    report.batch_id = batch_id
    report.status = "SUCCESS"
    report.message = ("导入完成"
                      + (f"，{len(warnings)} 条警告需复核" if warnings else ""))
    progress("done", 100, report.message)
    report.elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
    return report


# ============================================================
# 4. 模板
# ============================================================
def build_template(battery_type: str = LIQUID) -> pd.DataFrame:
    """生成空模板（含标准中文字段与示例行）。"""
    specs = [s for s in FIELD_SPECS if battery_type in s.applies_to]
    cols = [s.name_cn for s in specs]
    if battery_type == LIQUID:
        example = ["MnO2", "金属氧化物", 1.82, 82.2, 28.6, 0.309, "GF/A(玻璃纤维)",
                   263.8, 0.777, "DOL/DME + 0.5M LiTFSI", 25, 0.1, 1000,
                   2.199, 927.5, 98.1, 96.08, 0.02]
    else:
        example = ["Li7P3S11", "硫化物", 22.3, 6.6, 1264.3, "PEO", 47.5,
                   25, 310.9, 1.0, 100, 1.2056, 79.2, 859.2, 92.3, 95.43, 2.37]
    return pd.DataFrame([example], columns=cols)


def template_to_excel(battery_type: str = LIQUID) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        build_template(battery_type).to_excel(w, index=False, sheet_name="导入模板")
    return buf.getvalue()
