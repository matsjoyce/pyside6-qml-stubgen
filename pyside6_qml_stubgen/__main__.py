"""
Generate QML stub files (.qmltypes) from Python modules (which use PySide6)

Usage:
    pyside6-qml-stubgen <in-dir>... --out-dir=<out-dir> [--ignore=<path>...] [--metatypes-dir=<dir>] [--qmltyperegistrar-path=<path>] [--force-rebuild] [--file-relative-path=<div>] [--extra-external-modules=<modules>]
    pyside6-qml-stubgen (-h | --help)
    pyside6-qml-stubgen --version

Options:
    --ignore=<path>                     Ignore all Python files that are children of this path
    --metatypes-dir=<dir>               Directory of the Qt 6 metatype files for core modules (automatically detected if not provided)
    --qmltyperegistrar-path=<path>      Path of the qmltyperegistrar tool (automatically detected if not provided)
    --force-rebuild                     Rebuild the stubs from scratch instead of doing a partial update
    --file-relative-path=<div>          Make all paths in generated type files relative to this path
                                            (useful for if the generated stubs need to be used on different systems)
    --extra-external-modules=<modules>  Additional modules which should be assumed to contain QML exposed types (comma separated)
    -h --help                           Show this screen
    --version                           Show version
"""

import pathlib

import docopt

from . import _version, process


def main() -> None:
    args = docopt.docopt(__doc__, version=_version.__version__)
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
        file_relative_path=(
            pathlib.Path(args["--file-relative-path"])
            if args["--file-relative-path"]
            else None
        ),
        force_rebuild=args["--force-rebuild"],
        extra_external_modules=(
            {m.strip() for m in args["--extra-external-modules"].split(",")}
            if args["--extra-external-modules"]
            else None
        ),
    )


if __name__ == "__main__":
    main()
