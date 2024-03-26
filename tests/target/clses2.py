from PySide6 import QtCore, QtQml


class UncreatableWithReason2(QtCore.QObject): ...


QtQml.qmlRegisterUncreatableType(
    UncreatableWithReason2, "target", 1, 0, "UncreatableWithReason2", "Don't make me"
)


class Named2(QtCore.QObject): ...


QtQml.qmlRegisterType(Named2, "target", 1, 0, "NamedSomethingDifferent2")


class Singleton2(QtCore.QObject): ...


QtQml.qmlRegisterSingletonType(Singleton2, "target", 1, 0, "Singleton2")


class Singleton3(QtCore.QObject):
    normChanged = QtCore.Signal(Named2, int, bool, name="normChanged")

    def getNorm(self) -> Named2: ...

    def setNorm(self, n: Named2) -> None: ...

    norm = QtCore.Property(Named2, getNorm, setNorm, notify=normChanged)


QtQml.qmlRegisterSingletonInstance(
    Singleton3, "target", 1, 0, "Singleton3", Singleton3()
)
