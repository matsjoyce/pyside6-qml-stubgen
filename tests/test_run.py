import filecmp
import pathlib

import pyside6_qml_stubgen

TARGET_DIR = pathlib.Path(__file__).parent / "target"
REFERENCE_DIR = pathlib.Path(__file__).parent / "reference"


def test_run_and_compare(tmp_path: pathlib.Path) -> None:
    pyside6_qml_stubgen.process(
        in_dir=TARGET_DIR.relative_to(pathlib.Path().resolve()),
        ignore_dirs=[],
        out_dir=tmp_path,
        metatypes_dir=None,
        qmltyperegistrar_path=None,
        file_relative_path=TARGET_DIR.parent.parent,
    )

    left = sorted(
        str(f.relative_to(REFERENCE_DIR))
        for f in REFERENCE_DIR.rglob("*")
        if f.is_file() and f.name != "README"
    )
    right = sorted(
        str(f.relative_to(tmp_path))
        for f in tmp_path.rglob("*")
        if f.is_file() and f.name != "README"
    )

    assert left == right

    match, mismatch, errors = filecmp.cmpfiles(
        REFERENCE_DIR,
        tmp_path,
        left,
        shallow=False,
    )

    assert mismatch == []
    assert errors == []
