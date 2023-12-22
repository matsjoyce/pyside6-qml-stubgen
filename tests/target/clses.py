from PySide6 import QtCore, QtGui, QtQml

QML_IMPORT_NAME = "target"
QML_IMPORT_MAJOR_VERSION = 1


@QtQml.QmlElement
@QtQml.QmlUncreatable()
class Uncreatable(QtCore.QObject):
    ...


@QtQml.QmlElement
@QtQml.QmlUncreatable("Don't make me!")
class UncreatableWithReason(QtCore.QObject):
    ...


@QtQml.QmlElement
class Normal(QtCore.QObject):
    ...


@QtQml.QmlNamedElement("NamedSomethingDifferent")
class Named(QtCore.QObject):
    ...


@QtQml.QmlAnonymous
class Anonymous(QtCore.QObject):
    ...


@QtQml.QmlElement
@QtQml.QmlSingleton
class Singleton(QtCore.QObject):
    ...


@QtQml.QmlElement
class SignalsAndProperties(QtGui.QStandardItemModel):
    @QtCore.Property(Anonymous, constant=True)
    def anon(self) -> Anonymous:
        ...

    normChanged = QtCore.Signal(Normal, int, bool, name="normChanged")

    @QtCore.Property(Normal, notify=normChanged)
    def norm(self) -> Normal:
        ...

    @norm.setter
    def norm(self, n: Normal) -> None:
        ...

    @QtCore.Slot(int, str, Normal)
    def slot1(self, x: int, y: str, z: Normal) -> None:
        ...
        ...

    @QtCore.Slot(result=Uncreatable)
    def slot2(self) -> Uncreatable:
        ...
