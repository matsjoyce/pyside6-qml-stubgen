from PySide6 import QtCore, QtQml

QML_IMPORT_NAME = "target.advanced"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 100


@QtQml.QmlAnonymous
class LayoutAttached(QtCore.QObject):
    @QtCore.Property(QtCore.QMargins)
    def margins(self): ...


@QtQml.QmlElement
@QtQml.QmlAttached(LayoutAttached)
class Layout(QtCore.QObject): ...


class LineEditorExtension(QtCore.QObject): ...


class LineEditor(QtCore.QObject): ...


@QtQml.QmlNamedElement("LineEditor")
@QtQml.QmlExtended(LineEditorExtension)
@QtQml.QmlForeign(LineEditor)
class LineEditorForeign(QtCore.QObject): ...
