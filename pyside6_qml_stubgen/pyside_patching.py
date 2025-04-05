import builtins
import collections
import contextlib
import dataclasses
import inspect
import types
import typing

from PySide6 import QtCore, QtQml

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
    module_dependencies: typing.DefaultDict[str, set[str]] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(set)
    )

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
        old_fn(type_obj, uri, version_major, version_minor, qml_name, callback)

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
        old_fn(
            type_obj,
            uri,
            version_major,
            version_minor,
            qml_name,
            *([callback] if callback else []),
        )

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
        old_fn(type_obj, uri, version_major, version_minor, qml_name)

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
        old_fn(type_obj, uri, version_major, version_minor, qml_name, message)


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

    @contextlib.contextmanager
    def module_in_globals(name: str, major: int, minor: int) -> typing.Iterator[None]:
        globals()["QML_IMPORT_NAME"] = name
        globals()["QML_IMPORT_MAJOR_VERSION"] = major
        globals()["QML_IMPORT_MINOR_VERSION"] = minor
        try:
            yield
        finally:
            del globals()["QML_IMPORT_NAME"]
            del globals()["QML_IMPORT_MAJOR_VERSION"]
            del globals()["QML_IMPORT_MINOR_VERSION"]

    @patch_with(QtQml)
    def QmlSingleton(
        cls: type[T_TypeQObject], *, old_fn: typing.Callable
    ) -> type[T_TypeQObject]:
        info.extra_class_infos[cls].append(("QML.Singleton", "true"))
        return old_fn(cls)

    @patch_with(QtQml)
    def QmlElement(
        cls: type[T_TypeQObject], *, old_fn: typing.Callable
    ) -> type[T_TypeQObject]:
        info.extra_class_infos[cls].append(("QML.Element", "auto"))
        mod_info = get_module()
        info.add_cls(*mod_info, cls)
        with module_in_globals(*mod_info):
            return old_fn(cls)

    @patch_with(QtQml)
    def QmlAnonymous(
        cls: type[T_TypeQObject], *, old_fn: typing.Callable
    ) -> type[T_TypeQObject]:
        info.extra_class_infos[cls].append(("QML.Element", "anonymous"))
        mod_info = get_module()
        info.add_cls(*mod_info, cls)
        with module_in_globals(*mod_info):
            return old_fn(cls)

    @patch_with(QtQml)
    def QmlNamedElement(
        name: str, *, old_fn: typing.Callable
    ) -> typing.Callable[[type[T_TypeQObject]], type[T_TypeQObject]]:
        def w(cls: type[T_TypeQObject]) -> type[T_TypeQObject]:
            info.extra_class_infos[cls].append(("QML.Element", name))
            mod_info = get_module(stack_levels=2)
            info.add_cls(*mod_info, cls)
            with module_in_globals(*mod_info):
                return old_fn(name)(cls)

        return w

    @patch_with(QtQml)
    def QmlUncreatable(
        reason: str | None = None, *, old_fn: typing.Callable
    ) -> typing.Callable[[type[T_TypeQObject]], type[T_TypeQObject]]:
        def w(cls: type[T_TypeQObject]) -> type[T_TypeQObject]:
            info.extra_class_infos[cls].append(("QML.Creatable", "false"))
            if reason is not None:
                info.extra_class_infos[cls].append(("QML.UncreatableReason", reason))

            return old_fn(reason)(cls)

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
            return old_fn(type_obj)(cls)

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
            return old_fn(type_obj)(cls)

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
            return old_fn(type_obj)(cls)

        return w


def patch_meta_system(info: ExtraCollectedInfo) -> None:
    @patch_with(QtCore)
    def ClassInfo(
        *args: typing.Mapping[str, str], old_fn: typing.Callable, **kwargs: str
    ) -> typing.Callable[[type[T_TypeQObject]], type[T_TypeQObject]]:
        def w(cls: type[T_TypeQObject]) -> type[T_TypeQObject]:
            infos = dict(collections.ChainMap(*map(dict, args), kwargs))
            for n, k in infos.items():
                info.extra_class_infos[cls].append((n, k))

            return old_fn(infos)(cls)

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


def patch_builtins(info: ExtraCollectedInfo) -> None:
    @patch_with(builtins)
    def __orig_import__(
        name: str,
        globals: typing.Mapping[str, object] | None = None,
        locals: typing.Mapping[str, object] | None = None,
        fromlist: typing.Sequence[str] | None = None,
        level: int = 0,
        *,
        old_fn: typing.Callable,
    ) -> types.ModuleType:
        calling_module = (globals or locals or {}).get("__name__")
        mod = old_fn(name, globals, locals, fromlist, level)
        if isinstance(calling_module, str):
            info.module_dependencies[calling_module].add(mod.__name__)
            for fromname in fromlist or ():
                if isinstance(
                    frommod := getattr(mod, fromname, None), types.ModuleType
                ):
                    info.module_dependencies[calling_module].add(frommod.__name__)
        return mod


def patches() -> ExtraCollectedInfo:
    info = ExtraCollectedInfo()

    patch_functions(info)
    patch_class_decorators(info)
    patch_meta_system(info)
    patch_builtins(info)

    return info
