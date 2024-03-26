from PySide6 import QtCore, QtQml


class LayoutAttached2(QtCore.QObject):
    @QtCore.Property(QtCore.QMargins)
    def margins(self): ...


QtQml.qmlRegisterType(LayoutAttached2, "target.advanced2", 1, 100, "LayoutAttached2")


@QtQml.QmlAttached(LayoutAttached2)
class Layout2(QtCore.QObject): ...


QtQml.qmlRegisterType(Layout2, "target.advanced2", 1, 100, "Layout2")


class LineEditorExtension2(QtCore.QObject): ...


class LineEditor2(QtCore.QObject): ...


@QtQml.QmlExtended(LineEditorExtension2)
@QtQml.QmlForeign(LineEditor2)
class LineEditorForeign2(QtCore.QObject): ...


QtQml.qmlRegisterType(LineEditorForeign2, "target.advanced2", 1, 100, "LineEditor2")
