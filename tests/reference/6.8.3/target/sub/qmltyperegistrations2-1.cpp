/****************************************************************************
** Generated QML type registration code
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <QtQml/qqml.h>
#include <QtQml/qqmlmoduleregistration.h>

#if __has_include(<in/submodule.py>)
#  include <in/submodule.py>
#endif


#if !defined(QT_STATIC)
#define Q_QMLTYPE_EXPORT Q_DECL_EXPORT
#else
#define Q_QMLTYPE_EXPORT
#endif
Q_QMLTYPE_EXPORT void qml_register_types_target_sub()
{
    qmlRegisterModule("target.sub", 2, 0);
    QT_WARNING_PUSH QT_WARNING_DISABLE_DEPRECATED
    qmlRegisterTypesAndRevisions<Obj>("target.sub", 2);
    QT_WARNING_POP
    qmlRegisterModule("target.sub", 2, 1);
}

static const QQmlModuleRegistration targetsubRegistration("target.sub", qml_register_types_target_sub);
