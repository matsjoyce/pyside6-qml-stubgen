from PySide6 import QtCore, QtQml

from . import clses

QML_IMPORT_NAME = "target.sub"
QML_IMPORT_MAJOR_VERSION = 2
QML_IMPORT_MINOR_VERSION = 1


@QtQml.QmlElement
class Obj(QtCore.QObject):
    @QtCore.Property(clses.Anonymous, constant=True)
    def anon(self) -> clses.Anonymous: ...
