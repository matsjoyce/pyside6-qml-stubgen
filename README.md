pyside6-qml-stubgen
===================

Generate QML stub files (`.qmltypes`) from Python modules (which use PySide6)

Installation
------------

This tool is not yet distributed though pip, so instead clone the repo and then install using pip:

```bash
git clone https://github.com/matsjoyce/pyside6-qml-stubgen.git
pip install ./pyside6-qml-stubgen
```

Simple example
--------------

As an example, we'll run this tool on https://github.com/matsjoyce/fantasia2. There are two steps to type checking your QML code when using PySide6. First generate the QML type stubs using this tool:

```bash
pyside6-qml-stubgen fantasia2 --out-dir qmltypes --ignore fantasia2/alembic/
```

This command will generate a folder tree containing `.qmltypes` files and `qmldir` files matching the runtime structure of QML modules registered by the Python modules.

The second step is to run `qmllint` on your QML files using the type stubs:

```bash
/usr/lib/qt6/bin/qmllint fantasia2/*.qml -I ./qmltypes
```

If you change the QML files, you can just rerun `qmllint`. If you change the Python interface, you should rerun both commands.

Links to other projects
-----------------------

This tool relies heavily on PySide6, and is inspired by the [`metaobjectdump.py`](https://code.qt.io/cgit/pyside/pyside-setup.git/tree/sources/pyside-tools/metaobjectdump.py) tool, although this tool uses a runtime approach instead of static analysis, as that works better on large programs.

This tool has been tested on Arch Linux, and should run on other Linux distributions (although you may need to provide some paths to the tool using the command-line flags if the defaults are not correct).

This tool does not run on Windows yet (but I will be working on it soon). It does not run with PyQt6 either, although it should be possible in theory (send a PR if you get it working). And finally, it does not run using Qt 5 (PySide2 or PyQt5), as that version is no longer being developed, and QML in Qt 5 has less features than in Qt 6.

Command-line arguments
----------------------

```bash
$ pyside6-qml-stubgen --help
Generate QML stub files (.qmltypes) from Python modules (which use PySide6)

Usage:
    pyside6-qml-stubgen <in-dir> --out-dir=<out-dir> [--ignore=<path>...] [--metatypes-dir=<dir>] [--qmltyperegistrar-path=<path>]

Options:
    --ignore=<path>                     Ignore all Python files that are children of thispath
    --metatypes-dir=<dir>               Directory of the Qt 6 metatype files for core modules [default: /usr/lib/qt6/metatypes]
    --qmltyperegistrar-path=<path>      Path of the qmltyperegistrar tool [default: /usr/lib/qt6/qmltyperegistrar]
```
