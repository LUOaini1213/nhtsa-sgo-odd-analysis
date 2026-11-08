"""io_utils.read_clean 的布尔列解析，以及 check_tables.py 能发现行尾/数值差异。"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


io_utils = _load("io_utils")


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "clean.csv"
    p.write_text(body, encoding="utf-8-sig", newline="")
    return p


def test_read_clean_parses_bools(tmp_path):
    df = io_utils.read_clean(_write(tmp_path, "rain,engaged,speed_mph\nTrue,False,12\nFalse,True,\n"))
    assert df["rain"].tolist() == [True, False]
    assert df["engaged"].tolist() == [False, True]
    assert df["speed_mph"].isna().tolist() == [False, True]


@pytest.mark.parametrize("bad", ["", "true", "1", "Unknown"])
def test_read_clean_rejects_unexpected_bool_values(tmp_path, bad):
    # 以前 astype(bool) 会把这些值悄悄变成 True
    with pytest.raises(ValueError, match="rain_or_wet"):
        io_utils.read_clean(_write(tmp_path, f"rain_or_wet,hour\nTrue,1\n{bad},2\n"))


def test_to_csv_calls_pin_lf_line_endings():
    for f in sorted((ROOT / "scripts").glob("0*.py")):
        text = f.read_text(encoding="utf-8")
        n_calls = text.count(".to_csv(")
        assert text.count('lineterminator="\\n"') == n_calls, f"{f.name}: 每个 to_csv 都要写 lineterminator='\\n'"


def _git_available() -> bool:
    try:
        subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


@pytest.mark.skipif(not _git_available(), reason="需要 git 仓库")
def test_check_tables_detects_crlf_and_value_change(tmp_path):
    # 在临时克隆里改坏一张表，check_tables.py 必须返回 1；还原后返回 0
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(ROOT), str(clone)], check=True)
    script = clone / "scripts" / "check_tables.py"
    shutil.copyfile(ROOT / "scripts" / "check_tables.py", script)  # 用工作区的最新版本

    def run() -> int:
        return subprocess.run([sys.executable, "-I", "-B", "-X", "utf8", str(script)],
                              cwd=clone, capture_output=True).returncode

    assert run() == 0
    table = clone / "output" / "tables" / "key_metrics.csv"
    orig = table.read_bytes()
    table.write_bytes(orig.replace(b"\n", b"\r\n"))
    assert run() == 1
    table.write_bytes(orig.replace(b"K14,ADS,", b"K14,ADS,X", 1))
    assert run() == 1
    table.write_bytes(orig)
    (clone / "output" / "tables" / "extra.csv").write_bytes(b"a\n1\n")
    assert run() == 1
