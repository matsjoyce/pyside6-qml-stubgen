import collections
import importlib
import inspect
import itertools
import pathlib
import shlex
import shutil
import subprocess
import sys
import types
import typing

from PySide6 import QtCore

from . import dirty_file_detection, pyside_patching, qmlregistrar_types
from ._version import __version__, __version_tuple__


def parse_module(
    major: int,
    minor: int,
    clses: set[type[QtCore.QObject]],
    extra_info: pyside_patching.ExtraCollectedInfo,
    file_relative_path: pathlib.Path | None,
    extra_external_modules: set[str],
) -> typing.Sequence[qmlregistrar_types.Module]:
    ret = []
    for cls in clses:
        depends_on: set[str] = set()
        input_file = pathlib.Path(sys.modules[cls.__module__].__file__ or "").resolve()
        if file_relative_path is not None:
            input_file = input_file.relative_to(file_relative_path)
        ret.append(
            qmlregistrar_types.Module(
                classes=[parse_class(cls, depends_on, extra_info)],
                outputRevision=68,
                QML_IMPORT_MAJOR_VERSION=major,
                QML_IMPORT_MINOR_VERSION=minor,
                QT_MODULES=sorted(
                    [
                        dep.removeprefix("PySide6.")
                        for dep in extra_info.module_dependencies[cls.__module__]
                        if dep.startswith("PySide6.") or dep in extra_external_modules
                    ]
                ),
                PY_MODULES=list(depends_on),
                inputFile=input_file.as_posix(),
            )
        )
    return ret


def parse_class(
    cls: type[QtCore.QObject],
    depends_on: set[str],
    extra_info: pyside_patching.ExtraCollectedInfo,
) -> qmlregistrar_types.Class:
    meta = cls.staticMetaObject  # type: ignore[attr-defined]

    for base_cls in cls.__bases__:
        if module := extra_info.lookup_cls_module(base_cls):
            depends_on.add(module)

    return qmlregistrar_types.Class(
        className=meta.className(),
        qualifiedClassName=cls.__qualname__,
        object=True,
        superClasses=[
            qmlregistrar_types.SuperClass(
                access="public", name=meta.superClass().className()
            )
        ],
        classInfos=(
            [
                parse_class_info(meta.classInfo(i))
                for i in range(meta.classInfoOffset(), meta.classInfoCount())
            ]
            + [
                qmlregistrar_types.ClassInfo(name=n, value=v)
                for n, v in extra_info.extra_class_infos[cls]
            ]
        ),
        enums=[
            parse_enum(meta.enumerator(i))
            for i in range(meta.enumeratorOffset(), meta.enumeratorCount())
        ],
        properties=[
            parse_property(meta.property(i), cls, depends_on, extra_info)
            for i in range(meta.propertyOffset(), meta.propertyCount())
        ],
        signals=[
            parse_method(meta.method(i), cls, depends_on, extra_info)
            for i in range(meta.methodOffset(), meta.methodCount())
            if meta.method(i).methodType() == QtCore.QMetaMethod.MethodType.Signal
        ],
        slots=[
            parse_method(meta.method(i), cls, depends_on, extra_info)
            for i in range(meta.methodOffset(), meta.methodCount())
            if meta.method(i).methodType() == QtCore.QMetaMethod.MethodType.Slot
        ],
    )


def parse_class_info(cls_info: QtCore.QMetaClassInfo) -> qmlregistrar_types.ClassInfo:
    return qmlregistrar_types.ClassInfo(
        name=str(cls_info.name()), value=str(cls_info.value())
    )


def parse_enum(enum: QtCore.QMetaEnum) -> qmlregistrar_types.Enum:
    return qmlregistrar_types.Enum(
        isClass=enum.isScoped(),
        isFlag=enum.isFlag(),
        name=str(enum.enumName()),
        type="quint16",
        values=[str(enum.key(i)) for i in range(enum.keyCount())],
    )


def resolve_type_name(
    qt_name: str,
    py_type: type[QtCore.QObject] | str | None,
    depends_on: set[str],
    extra_info: pyside_patching.ExtraCollectedInfo,
) -> str:
    if isinstance(py_type, type) and issubclass(py_type, QtCore.QObject):
        if module := extra_info.lookup_cls_module(py_type):
            depends_on.add(module)
        return f"{py_type.staticMetaObject.className()}*"  # type: ignore[attr-defined]
    else:
        return qt_name


def parse_property(
    prop: QtCore.QMetaProperty,
    cls: type[QtCore.QObject],
    depends_on: set[str],
    extra_info: pyside_patching.ExtraCollectedInfo,
) -> qmlregistrar_types.Property:
    p = getattr(cls, str(prop.name()))
    t = p.fget._type
    return qmlregistrar_types.Property(
        name=str(prop.name()),
        type=resolve_type_name(
            prop.typeName(), t, depends_on, extra_info  # type: ignore[arg-type]
        ),
        index=prop.propertyIndex(),
        notify=(
            bytes(prop.notifySignal().name().data()).decode()
            if prop.hasNotifySignal()
            else None
        ),
        read=p.fget.__name__ if prop.isReadable() and p.fget else None,
        write=p.fset.__name__ if prop.isWritable() and p.fset else None,
    )


def parse_method(
    meth: QtCore.QMetaMethod,
    cls: type[QtCore.QObject],
    depends_on: set[str],
    extra_info: pyside_patching.ExtraCollectedInfo,
) -> qmlregistrar_types.Method:
    m = getattr(cls, bytes(meth.name().data()).decode())
    ts = extra_info.signal_types[m]
    try:
        param_names: typing.Iterable[str] = list(inspect.signature(m).parameters)[1:]
    except ValueError:
        param_names = itertools.cycle([""])
    return qmlregistrar_types.Method(
        access="public",
        name=bytes(meth.name().data()).decode(),
        arguments=[
            qmlregistrar_types.Argument(
                name=bytes(meth.parameterNames()[i].data()).decode() or n,
                type=resolve_type_name(
                    bytes(meth.parameterTypeName(i).data()).decode(),
                    t,
                    depends_on,
                    extra_info,
                ),
            )
            for i, t, n in zip(range(meth.parameterCount()), ts[0], param_names)
        ],
        returnType=resolve_type_name(meth.typeName(), ts[1], depends_on, extra_info),  # type: ignore[arg-type]
    )


def detect_metatypes_dir() -> pathlib.Path:
    for option in [
        pathlib.Path(QtCore.__file__).parent / "Qt" / "metatypes",
        pathlib.Path(QtCore.__file__).parent / "metatypes",
        pathlib.Path("/usr/lib/qt6/metatypes"),
    ]:
        if option.is_dir():
            return option

    raise RuntimeError(
        "Could not find metatypes dir. Provide it manually using the --metatypes-dir option"
    )


def detect_qmltyperegistrar_path() -> pathlib.Path:
    for option in [
        pathlib.Path(QtCore.__file__).parent / "Qt" / "libexec" / "qmltyperegistrar",
        pathlib.Path(QtCore.__file__).parent / "qmltyperegistrar.exe",
        pathlib.Path("/usr/lib/qt6/qmltyperegistrar"),
    ]:
        if option.is_file():
            return option

    raise RuntimeError(
        "Could not find qmltyperegistrar. Provide it manually using the --qmltyperegistrar-path option"
    )


def import_dirty_modules(
    in_dirs: typing.Sequence[pathlib.Path],
    ignore_dirs: typing.Sequence[pathlib.Path],
    out_dir: pathlib.Path,
) -> tuple[pyside_patching.ExtraCollectedInfo, set[pathlib.Path]]:
    extra_info = pyside_patching.patches()
    sys.path.append(".")
    sys_paths = sorted(
        [pathlib.Path(p).resolve() for p in sys.path if pathlib.Path(p).is_dir()],
        key=lambda p: len(p.parts),
        reverse=True,
    )

    all_python_files = [
        fname.resolve()
        for fname in itertools.chain.from_iterable(
            in_dir.rglob(suffix) for in_dir in in_dirs for suffix in ("*.py", "*.pyd")
        )
        if not any(ig in fname.parents for ig in ignore_dirs)
    ]
    (
        dirty_files,
        module_metadata,
        dependency_dirty_paths,
    ) = dirty_file_detection.detect_new_and_dirty_files(
        all_python_files, dirty_file_detection.load_modules_metadata(out_dir)
    )
    for fname, reason in dirty_files.items():
        relative_fname = fname
        for sys_p in sys_paths:
            if sys_p in fname.parents:
                relative_fname = fname.relative_to(sys_p)
                break
        else:
            raise RuntimeError(f"Could not deduce import name for {fname}")

        module = ".".join(
            [x.name for x in relative_fname.parents if x.name][::-1]
            + [relative_fname.name.split(".")[0]]
        )
        if module.endswith(".__init__"):
            module = module.removesuffix(".__init__")

        print(f" -> {module} ({reason})")
        mod = importlib.import_module(module)
        if not mod.__file__ or pathlib.Path(mod.__file__).resolve() != fname:
            raise RuntimeError(
                f"Imported module {module} was expected to come from {fname}, but instead came from {mod.__file__}"
            )
        dirty_file_detection.recursive_module_metadata_addition(
            module, extra_info.module_dependencies, module_metadata
        )

    dirty_file_detection.save_modules_metadata(
        out_dir,
        dirty_file_detection.PythonModulesMetadata(
            module_metadata, generating_version=__version__
        ),
    )

    extra_info.resolve_delayed()
    return (
        extra_info,
        {
            cf
            for cf in dirty_file_detection.imported_files()
            .union(dirty_files)
            .union(dependency_dirty_paths)
        },
    )


def update_qmlregistrar_files(
    extra_info: pyside_patching.ExtraCollectedInfo,
    dirty_files: set[pathlib.Path],
    out_dir: pathlib.Path,
    metatypes_dir: pathlib.Path,
    qmltyperegistrar_path: pathlib.Path,
    file_relative_path: pathlib.Path | None,
    extra_external_modules: set[str],
) -> None:
    # Find all QML modules that exist
    modules_to_process = set(extra_info.registered_classes)
    for types_path in out_dir.rglob("types*.json"):
        uri = ".".join(types_path.relative_to(out_dir).parent.parts)
        major, minor = map(int, types_path.stem.removeprefix("types").split("-"))
        modules_to_process.add((uri, major, minor))

    # Iterate though each QML module and update the qmlregistrar file (or remove it)
    foreign_types = [
        ft
        for ft in metatypes_dir.glob("*_metatypes.json")
        # QtGraphs duplicates a lot of type names from QtDataVisualization and QtCharts
        # Fixing this properly involves somehow working out which metatypes files are needed,
        # so work around this for now by just not including the old modules
        if "qt6datavisualization" not in ft.name and "qt6charts" not in ft.name
    ]
    dirty_type_dirs = []
    qmldir_entries = collections.defaultdict(set)
    for uri, major, minor in modules_to_process:
        out_path = out_dir / uri.replace(".", "/")
        types_json_file = out_path / f"types{major}-{minor}.json"
        out_path.mkdir(parents=True, exist_ok=True)

        if types_json_file.exists():
            original_data = qmlregistrar_types.read_qmlregistrar_file(types_json_file)
            data = [
                cls
                for cls in original_data
                if pathlib.Path(cls.inputFile).resolve() not in dirty_files
            ]
        else:
            original_data = []
            data = []

        clses = extra_info.registered_classes.get((uri, major, minor), set())
        data.extend(
            parse_module(
                major,
                minor,
                clses,
                extra_info,
                file_relative_path,
                extra_external_modules,
            )
        )
        data.sort(key=lambda cls: cls.classes[0].className)

        if len(data) == 0:
            # Got no types, module must have been removed, so remove the stubs
            types_json_file.unlink()
            types_json_file.with_name(
                f"qmltyperegistrations{major}-{minor}.cpp"
            ).unlink()
            types_json_file.with_suffix(".qmltypes").unlink()
            continue
        if original_data != data:
            # Types have changed, update the file and get a new qmltyperegistrar run
            dirty_type_dirs.append((uri, major, minor, out_path, len(clses)))
            qmlregistrar_types.write_qmlregistrar_file(types_json_file, data)

        foreign_types.append(types_json_file)
        qmldir_entries[out_path, uri].add(f"typeinfo types{major}-{minor}.qmltypes\n")
        for n in set(
            itertools.chain.from_iterable(
                [[*d.QT_MODULES, *d.PY_MODULES] for d in data]
            )
        ):
            qmldir_entries[out_path, uri].add(f"depends {n}\n")

    # Run qmltyperegistrar on all dirty modules
    for uri, major, minor, out_path, len_clses in dirty_type_dirs:
        print(f" -> {uri} {major}.{minor} (contains {len_clses} classes)")
        input_types_json = out_path / f"types{major}-{minor}.json"
        subprocess.run(
            [
                qmltyperegistrar_path,
                input_types_json,
                "-o",
                out_path / f"qmltyperegistrations{major}-{minor}.cpp",
                "--generate-qmltypes",
                out_path / f"types{major}-{minor}.qmltypes",
                "--import-name",
                uri,
                "--major-version",
                str(major),
                "--minor-version",
                str(minor),
                "--foreign-types",
                ",".join([str(ft) for ft in foreign_types if ft != input_types_json]),
            ],
            check=True,
        )

    # Remove all qmldirs
    for qmldir_path in out_dir.rglob("qmldir"):
        qmldir_path.unlink()

    # Regenerate qmldirs that should still exist
    for (out_path, uri), lines in qmldir_entries.items():
        with (out_path / "qmldir").open("w") as f:
            f.write(f"module {uri}\n")
            for line in sorted(lines):
                f.write(line)


def process(
    in_dirs: typing.Sequence[pathlib.Path],
    ignore_dirs: typing.Sequence[pathlib.Path],
    out_dir: pathlib.Path,
    metatypes_dir: pathlib.Path | None,
    qmltyperegistrar_path: pathlib.Path | None,
    *,
    file_relative_path: pathlib.Path | None = None,
    extra_external_modules: set[str] | None = None,
    force_rebuild: bool = False,
) -> None:
    if metatypes_dir is None:
        metatypes_dir = detect_metatypes_dir()
    if qmltyperegistrar_path is None:
        qmltyperegistrar_path = detect_qmltyperegistrar_path()

    if out_dir.exists() and force_rebuild:
        shutil.rmtree(out_dir)
    out_dir.mkdir(exist_ok=True)

    cmd = ["pyside6-qml-stubgen", *map(str, in_dirs), "--out-dir", str(out_dir)]
    for i in ignore_dirs:
        cmd.extend(["--ignore", str(i)])
    cmd.extend(
        [
            "--metatypes-dir",
            str(metatypes_dir),
            "--qmltyperegistrar-path",
            str(qmltyperegistrar_path),
        ]
    )
    if file_relative_path is not None:
        cmd.extend(["--file-relative-path", str(file_relative_path)])
    (out_dir / "README").write_text(
        f"QML type stubs generated automatically using\n{shlex.join(cmd)}"
    )

    print("Importing Python modules")
    extra_info, dirty_files = import_dirty_modules(in_dirs, ignore_dirs, out_dir)

    print("Generating QML type info for QML modules")
    update_qmlregistrar_files(
        extra_info,
        dirty_files,
        out_dir,
        metatypes_dir,
        qmltyperegistrar_path,
        file_relative_path,
        extra_external_modules or set(),
    )
