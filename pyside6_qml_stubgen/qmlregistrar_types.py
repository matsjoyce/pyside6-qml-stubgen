import dataclasses
import pathlib
import typing

import pydantic


@dataclasses.dataclass(frozen=True)
class Argument:
    name: str
    type: str


@dataclasses.dataclass(frozen=True)
class Method:
    access: typing.Literal["public"]
    name: str
    arguments: typing.Sequence[Argument]
    returnType: str


@dataclasses.dataclass(frozen=True)
class Property:
    name: str
    type: str
    index: int
    notify: str | None = None
    read: str | None = None
    write: str | None = None


@dataclasses.dataclass(frozen=True)
class Enum:
    isClass: bool
    isFlag: bool
    name: str
    type: str
    values: typing.Sequence[str]


@dataclasses.dataclass(frozen=True)
class ClassInfo:
    name: str
    value: str


@dataclasses.dataclass(frozen=True)
class SuperClass:
    access: typing.Literal["public"]
    name: str


@dataclasses.dataclass(frozen=True)
class Class:
    className: str
    qualifiedClassName: str
    object: bool
    superClasses: typing.Sequence[SuperClass]
    classInfos: typing.Sequence[ClassInfo]
    enums: typing.Sequence[Enum]
    properties: typing.Sequence[Property]
    signals: typing.Sequence[Method]
    slots: typing.Sequence[Method]


@dataclasses.dataclass(frozen=True)
class Module:
    classes: typing.Sequence[Class]
    outputRevision: typing.Literal[68]
    QML_IMPORT_MAJOR_VERSION: int
    QML_IMPORT_MINOR_VERSION: int
    QT_MODULES: typing.Sequence[str]
    PY_MODULES: typing.Sequence[str]
    inputFile: str


FILE_TYPE_ADAPTER: pydantic.TypeAdapter[typing.Sequence[Module]] = pydantic.TypeAdapter(
    typing.Sequence[Module]  # type: ignore[type-abstract]
)


def write_qmlregistrar_file(
    out_path: pathlib.Path, data: typing.Sequence[Module]
) -> None:
    with out_path.open("wb") as f:
        f.write(FILE_TYPE_ADAPTER.dump_json(data, indent=4, exclude_none=True))


def read_qmlregistrar_file(in_path: pathlib.Path) -> typing.Sequence[Module]:
    with in_path.open("rb") as f:
        return FILE_TYPE_ADAPTER.validate_json(f.read())
