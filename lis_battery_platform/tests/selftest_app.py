# -*- coding: utf-8 -*-
"""
Streamlit 冒烟测试（无头）
=========================
HTTP GET / 恒返回 200，不能用来判断脚本是否异常，必须用 AppTest 真跑一遍。
覆盖：默认分支 + 切换到固态分支 + 数据库开关分支。
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

TMP_DB = os.path.join(tempfile.gettempdir(), "bf_apptest.db")
os.environ["BF_DB_PATH"] = TMP_DB
for suffix in ("", "-wal", "-shm"):
    if os.path.exists(TMP_DB + suffix):
        os.remove(TMP_DB + suffix)

from streamlit.testing.v1 import AppTest       # noqa: E402

APP = os.path.join(PKG, "app.py")
ok = True


def run_case(name, mutate=None, timeout=1800):
    global ok
    at = AppTest.from_file(APP, default_timeout=timeout)
    at.run()
    if mutate:
        mutate(at)
        at.run()
    errs = [e for e in at.exception]
    if errs:
        ok = False
        print(f"[FAIL] {name}: {len(errs)} 个异常")
        for e in errs[:3]:
            print("       " + str(e.value)[:400])
    else:
        print(f"[PASS] {name}（无异常，元素 {len(at.main)} 个）")
    return at


print("=" * 60)
at1 = run_case("默认加载（液态，内置数据）")


def to_solid(at):
    at.radio[0].set_value("固态锂硫电池")


at2 = run_case("切换到固态体系", to_solid)


def enable_db(at):
    at.checkbox[0].set_value(True)


at3 = run_case("启用数据库开关", enable_db)

# Tab7 / Tab8 面板是否被渲染（通过文本断言）
at = at1
texts = " ".join(str(getattr(x, "value", "")) for x in at.markdown)
for key in ["批量数据导入", "精细化指标计算"]:
    hit = any(key in str(getattr(x, "value", "")) for x in at.markdown)
    print(f"[{'PASS' if hit else 'FAIL'}] 面板存在：{key}")
    ok = ok and hit

print("=" * 60)
print("结果：", "全部通过" if ok else "存在失败")
sys.exit(0 if ok else 1)
