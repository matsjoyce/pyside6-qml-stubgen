"""
Generate QML stub files (.qmltypes) from Python modules (which use PySide6)

Usage:
    pyside6-qml-stubgen <in-dir>... --out-dir=<out-dir> [--ignore=<path>...] [--metatypes-dir=<dir>] [--qmltyperegistrar-path=<path>]

Options:
    --ignore=<path>                     Ignore all Python files that are children of thispath
    --metatypes-dir=<dir>               Directory of the Qt 6 metatype files for core modules (automatically detected if not provided)
    --qmltyperegistrar-path=<path>      Path of the qmltyperegistrar tool (automatically detected if not provided)
"""

import pathlib

import docopt

from . import process


def main() -> None:
    args = docopt.docopt(__doc__)
    process(
        in_dirs=[pathlib.Path(p) for p in args["<in-dir>"]],
        ignore_dirs=[pathlib.Path(ig) for ig in args["--ignore"]],
        out_dir=pathlib.Path(args["--out-dir"]),
        metatypes_dir=(
            pathlib.Path(args["--metatypes-dir"]) if args["--metatypes-dir"] else None
        ),
        qmltyperegistrar_path=(
            pathlib.Path(args["--qmltyperegistrar-path"])
            if args["--qmltyperegistrar-path"]
            else None
        ),
    )


if __name__ == "__main__":
    main()
