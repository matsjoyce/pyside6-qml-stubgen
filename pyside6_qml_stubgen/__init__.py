import collections
import dataclasses
import importlib
import inspect
import itertools
import pathlib
import shutil
import subprocess
import sys
import types
import typing

from PySide6 import QtCore, QtQml

from . import dirty_file_detection, qmlregistrar_types

T_TypeQObject = typing.TypeVar("T_TypeQObject", bound=QtCore.QObject)


@dataclasses.dataclass
class ExtraCollectedInfo:
    extra_class_infos: typing.DefaultDict[
        type[QtCore.QObject], list[tuple[str, str]]
    ] = dataclasses.field(default_factory=lambda: collections.defaultdict(list))
    signal_types: dict[
        QtCore.Signal, tuple[tuple[type | str, ...], type | str | None]
    ] = dataclasses.field(default_factory=dict)
    registered_classes: typing.DefaultDict[
        tuple[str, int, int], set[type[QtCore.QObject]]
    ] = dataclasses.field(default_factory=lambda: collections.defaultdict(set))
    delayed_registrations: typing.DefaultDict[
        type[QtCore.QObject], set[type[QtCore.QObject]]
    ] = dataclasses.field(default_factory=lambda: collections.defaultdict(set))

    def lookup_cls_module(self, cls: type[QtCore.QObject]) -> str | None:
        for (uri, major, minor), clses in self.registered_classes.items():
            if cls in clses:
                return f"{uri} {major}.{minor}"
        return None

    def add_cls(
        self,
        uri: str,
        version_major: int,
        version_minor: int,
        type_obj: type[QtCore.QObject],
    ) -> None:
        self.registered_classes[uri, version_major, version_minor].add(type_obj)
        for base_cls in type_obj.__mro__:
            if isinstance(base_cls, type) and issubclass(base_cls, QtCore.QObject):
                self.delayed_registrations[type_obj].add(base_cls)

    def resolve_delayed(self) -> None:
        for cls, linked_clses in self.delayed_registrations.items():
            module = [k for k, v in self.registered_classes.items() if cls in v][0]
            for linked_cls in linked_clses:
                if self.lookup_cls_module(
                    linked_cls
                ) is None and not linked_cls.__module__.startswith("PySide6"):
                    self.registered_classes[module].add(linked_cls)
        self.delayed_registrations.clear()


def patch_with(mod: types.ModuleType) -> typing.Callable[[typing.Callable], None]:
    def w(fn: typing.Callable) -> None:
        name = fn.__name__
        old = getattr(mod, name)
        setattr(mod, name, lambda *args, **kwargs: fn(*args, **kwargs, old_fn=old))

    return w


def patch_functions(info: ExtraCollectedInfo) -> None:
    @patch_with(QtQml)
    def qmlRegisterSingletonInstance(
        type_obj: type[QtCore.QObject],
        uri: str,
        version_major: int,
        version_minor: int,
        qml_name: str,
        callback: object,
        *,
        old_fn: typing.Callable,
    ) -> None:
        info.extra_class_infos[type_obj].append(("QML.Singleton", "true"))
        info.extra_class_infos[type_obj].append(("QML.Element", qml_name))
        info.add_cls(uri, version_major, version_minor, type_obj)

    @patch_with(QtQml)
    def qmlRegisterSingletonType(
        type_obj: type[QtCore.QObject],
        uri: str,
        version_major: int,
        version_minor: int,
        qml_name: str,
        callback: object = None,
        *,
        old_fn: typing.Callable,
    ) -> None:
        info.extra_class_infos[type_obj].append(("QML.Singleton", "true"))
        info.extra_class_infos[type_obj].append(("QML.Element", qml_name))
        info.add_cls(uri, version_major, version_minor, type_obj)

    @patch_with(QtQml)
    def qmlRegisterType(
        type_obj: type[QtCore.QObject],
        uri: str,
        version_major: int,
        version_minor: int,
        qml_name: str,
        *,
        old_fn: typing.Callable,
    ) -> None:
        info.extra_class_infos[type_obj].append(("QML.Element", qml_name))
        info.add_cls(uri, version_major, version_minor, type_obj)

    @patch_with(QtQml)
    def qmlRegisterUncreatableMetaObject(
        staticMetaObject: QtCore.QMetaObject,
        uri: str,
        versionMajor: int,
        versionMinor: int,
        qmlName: str,
        reason: str,
        *,
        old_fn: typing.Callable,
    ) -> None:
        raise RuntimeError("qmlRegisterUncreatableMetaObject not supported yet")

    @patch_with(QtQml)
    def qmlRegisterUncreatableType(
        type_obj: type[QtCore.QObject],
        uri: str,
        version_major: int,
        version_minor: int,
        qml_name: str,
        message: str,
        *,
        old_fn: typing.Callable,
    ) -> None:
        info.extra_class_infos[type_obj].append(("QML.Creatable", "false"))
        info.extra_class_infos[type_obj].append(("QML.UncreatableReason", message))
        info.extra_class_infos[type_obj].append(("QML.Element", qml_name))
        info.add_cls(uri, version_major, version_minor, type_obj)


def patch_class_decorators(info: ExtraCollectedInfo) -> None:
    def go_up(frame: types.FrameType | None, levels: int) -> types.FrameType | None:
        if levels == 0:
            return frame
        return go_up(frame.f_back, levels - 1) if frame else None

    def get_module(stack_levels: int = 3) -> tuple[str, int, int]:
        frame = go_up(inspect.currentframe(), stack_levels)
        assert frame is not None, "No caller frame"
        glob = frame.f_globals
        name = glob["QML_IMPORT_NAME"]
        major = glob["QML_IMPORT_MAJOR_VERSION"]
        minor = glob.get("QML_IMPORT_MINOR_VERSION", 0)
        return name, major, minor

    @patch_with(QtQml)
    def QmlSingleton(
        cls: type[T_TypeQObject], *, old_fn: typing.Callable
    ) -> type[T_TypeQObject]:
        info.extra_class_infos[cls].append(("QML.Singleton", "true"))
        return cls

    @patch_with(QtQml)
    def QmlElement(
        cls: type[T_TypeQObject], *, old_fn: typing.Callable
    ) -> type[T_TypeQObject]:
        info.extra_class_infos[cls].append(("QML.Element", "auto"))
        info.add_cls(*get_module(), cls)
        return cls

    @patch_with(QtQml)
    def QmlAnonymous(
        cls: type[T_TypeQObject], *, old_fn: typing.Callable
    ) -> type[T_TypeQObject]:
        info.extra_class_infos[cls].append(("QML.Element", "anonymous"))
        info.add_cls(*get_module(), cls)
        return cls

    @patch_with(QtQml)
    def QmlNamedElement(
        name: str, *, old_fn: typing.Callable
    ) -> typing.Callable[[type[T_TypeQObject]], type[T_TypeQObject]]:
        def w(cls: type[T_TypeQObject]) -> type[T_TypeQObject]:
            info.extra_class_infos[cls].append(("QML.Element", name))
            info.add_cls(*get_module(stack_levels=2), cls)
            return cls

        return w

    @patch_with(QtQml)
    def QmlUncreatable(
        reason: str | None = None, *, old_fn: typing.Callable
    ) -> typing.Callable[[type[T_TypeQObject]], type[T_TypeQObject]]:
        def w(cls: type[T_TypeQObject]) -> type[T_TypeQObject]:
            info.extra_class_infos[cls].append(("QML.Creatable", "false"))
            if reason is not None:
                info.extra_class_infos[cls].append(("QML.UncreatableReason", reason))

            return cls

        return w

    @patch_with(QtQml)
    def QmlForeign(
        type_obj: type[T_TypeQObject], *, old_fn: typing.Callable
    ) -> typing.Callable[[type[T_TypeQObject]], type[T_TypeQObject]]:
        def w(cls: type[T_TypeQObject]) -> type[T_TypeQObject]:
            try:
                module = get_module(stack_levels=4)
            except KeyError:
                info.delayed_registrations[cls].add(type_obj)
            else:
                info.add_cls(*module, cls)
            info.extra_class_infos[cls].append(
                ("QML.Foreign", type_obj.staticMetaObject.className())  # type: ignore[attr-defined]
            )
            return cls

        return w

    @patch_with(QtQml)
    def QmlExtended(
        type_obj: type[T_TypeQObject], *, old_fn: typing.Callable
    ) -> typing.Callable[[type[T_TypeQObject]], type[T_TypeQObject]]:
        def w(cls: type[T_TypeQObject]) -> type[T_TypeQObject]:
            try:
                module = get_module(stack_levels=4)
            except KeyError:
                info.delayed_registrations[cls].add(type_obj)
            else:
                info.add_cls(*module, cls)
            info.extra_class_infos[cls].append(
                ("QML.Extended", type_obj.staticMetaObject.className())  # type: ignore[attr-defined]
            )
            return cls

        return w

    @patch_with(QtQml)
    def QmlAttached(
        type_obj: type[T_TypeQObject], *, old_fn: typing.Callable
    ) -> typing.Callable[[type[T_TypeQObject]], type[T_TypeQObject]]:
        def w(cls: type[T_TypeQObject]) -> type[T_TypeQObject]:
            try:
                module = get_module(stack_levels=4)
            except KeyError:
                info.delayed_registrations[cls].add(type_obj)
            else:
                info.add_cls(*module, cls)
            info.extra_class_infos[cls].append(
                ("QML.Attached", type_obj.staticMetaObject.className())  # type: ignore[attr-defined]
            )
            return cls

        return w


def patch_meta_system(info: ExtraCollectedInfo) -> None:
    @patch_with(QtCore)
    def ClassInfo(
        *args: typing.Mapping[str, str], old_fn: typing.Callable, **kwargs: str
    ) -> typing.Callable[[type[T_TypeQObject]], type[T_TypeQObject]]:
        def w(cls: type[T_TypeQObject]) -> type[T_TypeQObject]:
            for arg in args:
                for n, k in arg.items():
                    info.extra_class_infos[cls].append((n, k))
            for n, k in kwargs.items():
                info.extra_class_infos[cls].append((n, k))

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
            info.signal_types[f] = (types, result)  # type: ignore[index]
            return slot(f)

        return w

    QtSignal = QtCore.Signal

    class SignalMeta(type):
        def __subclasscheck__(self, subclass: type) -> bool:
            return issubclass(subclass, QtSignal)

        def __call__(self, *types: type | str, **kwargs: typing.Any) -> QtCore.Signal:
            sig = QtSignal(*types, **kwargs)  # type: ignore[arg-type]
            info.signal_types[sig] = (types, None)

            return sig

    class Signal(metaclass=SignalMeta):
        pass

    QtCore.Signal = Signal  # type: ignore[assignment,misc]


def patches() -> ExtraCollectedInfo:
    info = ExtraCollectedInfo()

    patch_functions(info)
    patch_class_decorators(info)
    patch_meta_system(info)

    return info


def parse_module(
    major: int,
    minor: int,
    clses: set[type[QtCore.QObject]],
    extra_info: ExtraCollectedInfo,
    file_relative_path: pathlib.Path | None,
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
                QT_MODULES=[
                    m.__name__.removeprefix("PySide6.")
                    for m in sys.modules[cls.__module__].__dict__.values()
                    if isinstance(m, types.ModuleType)
                    and m.__name__.startswith("PySide6.")
                ],
                PY_MODULES=list(depends_on),
                inputFile=input_file.as_posix(),
            )
        )
    return ret


def parse_class(
    cls: type[QtCore.QObject], depends_on: set[str], extra_info: ExtraCollectedInfo
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
    extra_info: ExtraCollectedInfo,
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
    extra_info: ExtraCollectedInfo,
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
    extra_info: ExtraCollectedInfo,
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
) -> tuple[ExtraCollectedInfo, set[pathlib.Path], set[pathlib.Path]]:
    extra_info = patches()
    sys.path.append(".")

    all_python_files = [
        fname
        for fname in itertools.chain.from_iterable(
            in_dir.rglob("*.py") for in_dir in in_dirs
        )
        if not any(ig in fname.parents for ig in ignore_dirs)
    ]
    dirty_files, module_metadata = dirty_file_detection.detect_new_and_dirty_files(
        all_python_files, dirty_file_detection.load_modules_metadata(out_dir)
    )
    imported_files: set[pathlib.Path] = set()
    for fname, reason in dirty_files.items():
        module = ".".join(
            [x.name for x in fname.parents if x.name][::-1] + [fname.stem]
        )
        if module.endswith(".__init__"):
            module = module.removesuffix(".__init__")
        print(f" -> {module} ({reason})")
        mod = importlib.import_module(module)
        if not mod.__file__ or pathlib.Path(mod.__file__).resolve() != fname.resolve():
            raise RuntimeError(
                f"Imported module {module} was expected to come from {fname}, but instead came from {mod.__file__}"
            )
        dirty_file_detection.recursive_module_metadata_addition(
            module, module_metadata, imported_files
        )

    dirty_file_detection.save_modules_metadata(
        out_dir, dirty_file_detection.PythonModulesMetadata(module_metadata)
    )

    extra_info.resolve_delayed()
    return (
        extra_info,
        {f.resolve() for f in all_python_files},
        {cf.resolve() for cf in imported_files.union(dirty_files)},
    )


def update_qmlregistrar_files(
    extra_info: ExtraCollectedInfo,
    all_files: set[pathlib.Path],
    dirty_files: set[pathlib.Path],
    out_dir: pathlib.Path,
    metatypes_dir: pathlib.Path,
    qmltyperegistrar_path: pathlib.Path,
    file_relative_path: pathlib.Path | None,
) -> None:
    # Find all QML modules that exist
    modules_to_process = set(extra_info.registered_classes)
    for types_path in out_dir.rglob("types*.json"):
        uri = ".".join(types_path.relative_to(out_dir).parent.parts)
        major, minor = map(int, types_path.stem.removeprefix("types").split("-"))
        modules_to_process.add((uri, major, minor))

    # Iterate though each QML module and update the qmlregistrar file (or remove it)
    foreign_types = list(metatypes_dir.glob("*_metatypes.json"))
    dirty_type_dirs = []
    qmldir_entries = collections.defaultdict(set)
    clean_files = all_files - dirty_files
    for uri, major, minor in modules_to_process:
        out_path = out_dir / uri.replace(".", "/")
        types_json_file = out_path / f"types{major}-{minor}.json"
        out_path.mkdir(parents=True, exist_ok=True)

        if types_json_file.exists():
            original_data = qmlregistrar_types.read_qmlregistrar_file(types_json_file)
            data = [
                cls
                for cls in original_data
                if pathlib.Path(cls.inputFile).resolve() in clean_files
            ]
        else:
            original_data = []
            data = []

        clses = extra_info.registered_classes.get((uri, major, minor), set())
        data.extend(parse_module(major, minor, clses, extra_info, file_relative_path))
        data.sort(key=lambda cls: cls.classes[0].className)
        for cls in data:
            if pathlib.Path(cls.inputFile).resolve() not in all_files:
                raise RuntimeError(
                    f"Found {cls.classes[0].className} registered for {uri} but the filename {cls.inputFile} is not in the files we scanned ({all_files})"
                )

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
        subprocess.run(
            [
                qmltyperegistrar_path,
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
    force_rebuild: bool = False,
) -> None:
    if metatypes_dir is None:
        metatypes_dir = detect_metatypes_dir()
    if qmltyperegistrar_path is None:
        qmltyperegistrar_path = detect_qmltyperegistrar_path()

    if out_dir.exists() and force_rebuild:
        shutil.rmtree(out_dir)
    out_dir.mkdir(exist_ok=True)
    (out_dir / "README").write_text(
        f"""QML type stubs generated automatically using
pyside6-qml-stubgen {' '.join(map(str, in_dirs))} --out-dir {out_dir} {' '.join(f'--ignore {i}' for i in ignore_dirs)} --metatypes-dir {metatypes_dir} --qmltyperegistrar-path {qmltyperegistrar_path}"""
    )

    print("Importing Python modules")
    extra_info, all_files, dirty_files = import_dirty_modules(
        in_dirs, ignore_dirs, out_dir
    )

    print("Generating QML type info for QML modules")
    update_qmlregistrar_files(
        extra_info,
        all_files,
        dirty_files,
        out_dir,
        metatypes_dir,
        qmltyperegistrar_path,
        file_relative_path,
    )
