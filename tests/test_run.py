import collections
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest
from PySide6 import QtCore

TARGET_DIR = pathlib.Path(__file__).parent / "target"
REFERENCE_DIR = pathlib.Path(__file__).parent / "reference" / QtCore.qVersion()

ROOT_PATH = pathlib.Path(__file__).parent.parent
WRITE_REFERENCE = False


def assert_dirs_equal(reference: pathlib.Path, result: pathlib.Path) -> None:
    ref_files = sorted(
        str(f.relative_to(reference))
        for f in reference.rglob("*")
        if f.is_file() and f.name not in {"README", "metadata.json"}
    )
    res_files = sorted(
        str(f.relative_to(result))
        for f in result.rglob("*")
        if f.is_file() and f.name not in {"README", "metadata.json"}
    )

    assert ref_files == res_files

    for f in ref_files:
        ref_text = (reference / f).read_text()
        res_text = (result / f).read_text().replace(os.sep, "/")
        assert ref_text == res_text, f


def run_stubgen(tmp_dir: pathlib.Path) -> None:
    # Needs to be run in it's own process since we rely on imports being fresh
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pyside6_qml_stubgen",
            "in",
            "--out-dir",
            "out",
            "--file-relative-path",
            tmp_dir,
        ],
        check=True,
        cwd=tmp_dir,
        env=collections.ChainMap({"PYTHONPATH": str(ROOT_PATH)}, os.environ),
    )


@pytest.fixture
def tmp_path_with_code(tmp_path: pathlib.Path) -> pathlib.Path:
    if WRITE_REFERENCE:
        REFERENCE_DIR.mkdir(exist_ok=True, parents=True)
    assert REFERENCE_DIR.exists(), f"Missing reference dir {REFERENCE_DIR}"
    (tmp_path / "in").mkdir()
    for path in TARGET_DIR.glob("*.py"):
        (tmp_path / "in" / path.name).write_text(path.read_text())
    shutil.copytree(REFERENCE_DIR, tmp_path / "ref")
    return tmp_path


def test_run_and_compare(tmp_path_with_code: pathlib.Path) -> None:
    run_stubgen(tmp_path_with_code)
    if WRITE_REFERENCE:
        shutil.rmtree(REFERENCE_DIR)
        shutil.copytree(tmp_path_with_code / "out", REFERENCE_DIR)
    assert not WRITE_REFERENCE, "Turn off reference generation"
    assert_dirs_equal(tmp_path_with_code / "ref", tmp_path_with_code / "out")


def test_run_and_compare_with_mtime_change(tmp_path_with_code: pathlib.Path) -> None:
    run_stubgen(tmp_path_with_code)
    (tmp_path_with_code / "in" / "clses2.py").write_bytes(
        (tmp_path_with_code / "in" / "clses2.py").read_bytes()
    )
    run_stubgen(tmp_path_with_code)
    assert_dirs_equal(tmp_path_with_code / "ref", tmp_path_with_code / "out")


def test_run_and_compare_with_deletion(tmp_path_with_code: pathlib.Path) -> None:
    run_stubgen(tmp_path_with_code)
    (tmp_path_with_code / "in" / "submodule.py").unlink()
    shutil.rmtree(tmp_path_with_code / "ref" / "target" / "sub")
    run_stubgen(tmp_path_with_code)
    assert_dirs_equal(tmp_path_with_code / "ref", tmp_path_with_code / "out")


def test_run_and_compare_with_change(tmp_path_with_code: pathlib.Path) -> None:
    run_stubgen(tmp_path_with_code)

    def replace_in(path: pathlib.Path) -> None:
        text = path.read_text()
        assert "getNorm" in text
        path.write_text(text.replace("getNorm", "getNorman"))

    replace_in(tmp_path_with_code / "in" / "clses2.py")
    for path in (tmp_path_with_code / "ref" / "target").iterdir():
        if path.suffix in {".json", ".qmltypes"}:
            replace_in(path)

    run_stubgen(tmp_path_with_code)
    assert_dirs_equal(tmp_path_with_code / "ref", tmp_path_with_code / "out")


def test_run_and_compare_with_addition(tmp_path_with_code: pathlib.Path) -> None:
    run_stubgen(tmp_path_with_code)

    def replace_in(path: pathlib.Path) -> None:
        text = path.read_text()
        path.write_text(
            re.sub("target.sub", r"\g<0>2", text)
            .replace("submodule.py", "submodule2.py")
            .replace("targetsubRegistration", "targetsub2Registration")
        )

    (tmp_path_with_code / "in" / "submodule2.py").write_text(
        (tmp_path_with_code / "in" / "submodule.py").read_text()
    )
    shutil.copytree(
        tmp_path_with_code / "ref" / "target" / "sub",
        tmp_path_with_code / "ref" / "target" / "sub2",
    )

    replace_in(tmp_path_with_code / "in" / "submodule2.py")
    for path in (tmp_path_with_code / "ref" / "target" / "sub2").iterdir():
        replace_in(path)

    run_stubgen(tmp_path_with_code)
    assert_dirs_equal(tmp_path_with_code / "ref", tmp_path_with_code / "out")
