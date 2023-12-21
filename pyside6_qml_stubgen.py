"""
Generate QML stub files (.qmltypes) from Python modules (which use PySide6)

Usage:
    pyside6-qml-stubgen <in-dir> --out-dir=<out-dir> [--ignore=<path>...] [--metatypes-dir=<dir>] [--qmltyperegistrar-path=<path>]

Options:
    --ignore=<path>                     Ignore all Python files that are children of thispath
    --metatypes-dir=<dir>               Directory of the Qt 6 metatype files for core modules [default: /usr/lib/qt6/metatypes]
    --qmltyperegistrar-path=<path>      Path of the qmltyperegistrar tool [default: /usr/lib/qt6/qmltyperegistrar]
"""

import collections
import dataclasses
import importlib
import inspect
import itertools
import json
import pathlib
import shutil
import subprocess
import sys
import types
import typing

import docopt
from PySide6 import QtCore, QtQml


@dataclasses.dataclass
class ExtraCollectedInfo:
    extra_class_infos: typing.DefaultDict[
        type[QtCore.QObject], list[tuple[str, str]]
    ] = dataclasses.field(default_factory=lambda: collections.defaultdict(list))
    signal_types: dict[
        typing.Callable, tuple[tuple[type | str, ...], type | str | None]
    ] = dataclasses.field(default_factory=dict)
    registered_classes: typing.DefaultDict[
        tuple[str, int, int], list[type[QtCore.QObject]]
    ] = dataclasses.field(default_factory=lambda: collections.defaultdict(list))


def patch_with(mod: types.ModuleType) -> typing.Callable[[typing.Callable], None]:
    def w(fn: typing.Callable) -> None:
        name = fn.__name__
        old = getattr(mod, name)
        setattr(mod, name, lambda *args, **kwargs: fn(*args, **kwargs, old_fn=old))

    return w


def patches() -> ExtraCollectedInfo:
    info = ExtraCollectedInfo()

    T_TypeQObject = typing.TypeVar("T_TypeQObject", bound=QtCore.QObject)

    def go_up(frame: types.FrameType | None) -> types.FrameType | None:
        return frame.f_back if frame else None

    def get_module() -> tuple[str, int, int]:
        frame = go_up(go_up(go_up(inspect.currentframe())))
        assert frame is not None, "No caller frame"
        glob = frame.f_globals
        name = glob["QML_IMPORT_NAME"]
        major = glob["QML_IMPORT_MAJOR_VERSION"]
        minor = glob.get("QML_IMPORT_MINOR_VERSION", 0)
        return name, major, minor

    @patch_with(QtQml)
    def qmlRegisterSingletonType(
        uri: str,
        major: int,
        minor: int,
        name: str,
        cls: type[T_TypeQObject],
        old_fn: typing.Callable,
    ) -> None:
        info.extra_class_infos[cls].append(("QML.Singleton", "true"))
        info.registered_classes[uri, major, minor].append(cls)

    @patch_with(QtQml)
    def qmlRegisterType(
        uri: str,
        major: int,
        minor: int,
        name: str,
        cls: type[T_TypeQObject],
        old_fn: typing.Callable,
    ) -> None:
        info.extra_class_infos[cls].append(("QML.Element", "auto"))

    @patch_with(QtQml)
    def QmlSingleton(
        cls: type[T_TypeQObject], old_fn: typing.Callable
    ) -> type[T_TypeQObject]:
        info.extra_class_infos[cls].append(("QML.Singleton", "true"))
        return cls

    @patch_with(QtQml)
    def QmlElement(
        cls: type[T_TypeQObject], old_fn: typing.Callable
    ) -> type[T_TypeQObject]:
        info.extra_class_infos[cls].append(("QML.Element", "auto"))
        info.registered_classes[get_module()].append(cls)
        return cls

    @patch_with(QtQml)
    def QmlUncreatable(
        reason: str | None = None, *, old_fn: typing.Callable
    ) -> typing.Callable[[type[T_TypeQObject]], type[T_TypeQObject]]:
        def w(cls: type[T_TypeQObject]) -> type[T_TypeQObject]:
            info.extra_class_infos[cls].append(("QML.Creatable", "false"))
            if reason is not None:
                info.extra_class_infos[cls].append(("QML.UncreatableReason", "true"))

            return cls

        return w

    @patch_with(QtCore)
    def Property(
        type: type | str,
        *args: typing.Any,
        old_fn: typing.Callable,
        **kwargs: typing.Any,
    ) -> typing.Callable[[typing.Callable], QtCore.Property] | QtCore.Property:
        prop = old_fn(type, *args, **kwargs)
        if prop.fget:
            prop.fget._type = type
        else:

            def w(fget: typing.Callable) -> QtCore.Property:
                fget._type = type  # type: ignore[attr-defined]
                return prop(fget)

            return w
        return prop

    @patch_with(QtCore)
    def Slot(
        *types: type | str,
        old_fn: typing.Callable,
        result: type | str | None = None,
        **kwargs: typing.Any,
    ) -> typing.Callable:
        slot = old_fn(*types, **kwargs)

        def w(f: typing.Callable) -> typing.Callable:
            info.signal_types[f] = (types, result)
            return slot(f)

        return w

    @patch_with(QtCore)
    def Signal(
        *types: type | str, old_fn: typing.Callable, **kwargs: typing.Any
    ) -> QtCore.Signal:
        sig = old_fn(*types, **kwargs)
        info.signal_types[sig] = (types, None)

        return sig

    return info


def parse_module(
    uri: str,
    major: int,
    minor: int,
    clses: typing.Sequence[type[QtCore.QObject]],
    extra_info: ExtraCollectedInfo,
) -> typing.Sequence[typing.Mapping]:
    ret = []
    for cls in clses:
        depends_on: set[str] = set()
        ret.append(
            {
                "classes": [parse_class(cls, depends_on, extra_info)],
                "outputRevision": 68,
                "QML_IMPORT_MAJOR_VERSION": 1,
                "QML_IMPORT_MINOR_VERSION": 0,
                "QT_MODULES": [
                    m.__name__.removeprefix("PySide6.")
                    for m in sys.modules[cls.__module__].__dict__.values()
                    if isinstance(m, types.ModuleType)
                    and m.__name__.startswith("PySide6.")
                ],
                "PY_MODULES": list(depends_on),
                "inputFile": sys.modules[cls.__module__].__file__,
            }
        )
    return ret


def parse_class(
    cls: type[QtCore.QObject], depends_on: set[str], extra_info: ExtraCollectedInfo
) -> typing.Mapping:
    meta = cls.staticMetaObject  # type: ignore[attr-defined]

    return {
        "className": meta.className(),
        "qualifiedClassName": cls.__qualname__,
        "object": True,
        "superClasses": [{"access": "public", "name": meta.superClass().className()}],
        "classInfos": (
            [
                parse_class_info(meta.classInfo(i))
                for i in range(meta.classInfoOffset(), meta.classInfoCount())
            ]
            + [{"name": n, "value": v} for n, v in extra_info.extra_class_infos[cls]]
        ),
        "enums": [
            parse_enum(meta.enumerator(i))
            for i in range(meta.enumeratorOffset(), meta.enumeratorCount())
        ],
        "properties": [
            parse_property(meta.property(i), cls, depends_on, extra_info)
            for i in range(meta.propertyOffset(), meta.propertyCount())
        ],
        "signals": [
            parse_method(meta.method(i), cls, depends_on, extra_info)
            for i in range(meta.methodOffset(), meta.methodCount())
            if meta.method(i).methodType() == QtCore.QMetaMethod.MethodType.Signal
        ],
        "slots": [
            parse_method(meta.method(i), cls, depends_on, extra_info)
            for i in range(meta.methodOffset(), meta.methodCount())
            if meta.method(i).methodType() == QtCore.QMetaMethod.MethodType.Slot
        ],
    }


def parse_class_info(cls_info: QtCore.QMetaClassInfo) -> typing.Mapping:
    return {"name": cls_info.name(), "value": cls_info.value()}


def parse_enum(enum: QtCore.QMetaEnum) -> typing.Mapping:
    return {
        "isClass": enum.isScoped(),
        "isFlag": enum.isFlag(),
        "name": enum.enumName(),
        "type": "quint16",
        "values": [enum.key(i) for i in range(enum.keyCount())],
    }


def resolve_type_name(
    qt_name: str,
    py_type: type[QtCore.QObject] | str | None,
    depends_on: set[str],
    extra_info: ExtraCollectedInfo,
) -> str:
    if isinstance(py_type, type) and py_type in extra_info.extra_class_infos:
        depends_on.add(py_type.__module__)
        return f"{py_type.__name__}*"
    else:
        return qt_name


def parse_property(
    prop: QtCore.QMetaProperty,
    cls: type[QtCore.QObject],
    depends_on: set[str],
    extra_info: ExtraCollectedInfo,
) -> typing.Mapping:
    p = getattr(cls, str(prop.name()))
    t = p.fget._type
    ret = {
        "name": prop.name(),
        "type": resolve_type_name(
            prop.typeName(), t, depends_on, extra_info  # type: ignore[arg-type]
        ),
        "index": prop.propertyIndex(),
    }
    if prop.hasNotifySignal():
        ret["notify"] = prop.notifySignal().name().data().decode()
    if prop.isReadable() and p.fget:
        ret["read"] = p.fget.__name__
    if prop.isWritable() and p.fset:
        ret["write"] = p.fset.__name__
    return ret


def parse_method(
    meth: QtCore.QMetaMethod,
    cls: type[QtCore.QObject],
    depends_on: set[str],
    extra_info: ExtraCollectedInfo,
) -> typing.Mapping:
    m = getattr(cls, meth.name().data().decode())
    ts = extra_info.signal_types[m]
    try:
        param_names: typing.Iterable[str] = list(inspect.signature(m).parameters)[1:]
    except ValueError:
        param_names = itertools.cycle("")
    return {
        "access": "public",
        "name": meth.name().data().decode(),
        "arguments": [
            {
                "name": meth.parameterNames()[i].data().decode() or n,
                "type": resolve_type_name(
                    meth.parameterTypeName(i).data().decode(), t, depends_on, extra_info
                ),
            }
            for i, t, n in zip(range(meth.parameterCount()), ts[0], param_names)
        ],
        "returnType": resolve_type_name(meth.typeName(), ts[1], depends_on, extra_info),  # type: ignore[arg-type]
    }


def main() -> None:
    args = docopt.docopt(__doc__)
    extra_info = patches()

    out_dir = pathlib.Path(args["--out-dir"])
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir()

    in_dir = pathlib.Path(args["<in-dir>"])
    ignore_paths = [pathlib.Path(ig) for ig in args["--ignore"]]

    foreign_types = list(pathlib.Path(args["--metatypes-dir"]).glob("*_metatypes.json"))
    type_dirs = []

    sys.path.append(".")

    for fname in in_dir.rglob("*.py"):
        if any(ig in fname.parents for ig in ignore_paths):
            continue
        module = ".".join(
            [x.name for x in fname.parents if x.name][::-1] + [fname.stem]
        )
        print("Importing Python module", module)
        importlib.import_module(module)

    for (uri, major, minor), clses in extra_info.registered_classes.items():
        print(
            "Processing types declared for QML module",
            uri,
            major,
            minor,
            "which contains",
            len(clses),
            "classes",
        )
        data = parse_module(uri, major, minor, clses, extra_info)

        out_path = out_dir / uri.replace(".", "/")
        out_path.mkdir(parents=True, exist_ok=True)
        type_dirs.append((uri, major, minor, out_path, data))
        foreign_types.append(out_path / f"types{major}-{minor}.json")
        with open(out_path / f"types{major}-{minor}.json", "w") as f:
            json.dump(data, f, indent=4)

    qmldir_entries = collections.defaultdict(set)

    for uri, major, minor, out_path, data in type_dirs:
        print("Generating QML type info for QML module", uri, major, minor)
        subprocess.run(
            [
                args["--qmltyperegistrar-path"],
                out_path / f"types{major}-{minor}.json",
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
                ",".join(map(str, foreign_types)),
            ]
        )
        qmldir_entries[out_path].add(f"typeinfo types{major}-{minor}.qmltypes\n")
        for n in set(
            itertools.chain.from_iterable(
                [d["QT_MODULES"] + d["PY_MODULES"] for d in data]
            )
        ):
            qmldir_entries[out_path].add(f"depends {n}\n")
    for out_path, lines in qmldir_entries.items():
        with (out_path / "qmldir").open("w") as f:
            f.write(f"module {module}\n")
            for line in lines:
                f.write(line)


if __name__ == "__main__":
    main()
