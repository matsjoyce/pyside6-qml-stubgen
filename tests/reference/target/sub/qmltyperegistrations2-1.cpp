/****************************************************************************
** Generated QML type registration code
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <QtQml/qqml.h>
#include <QtQml/qqmlmoduleregistration.h>

#include <tests/target/submodule.py>


#if !defined(QT_STATIC)
#define Q_QMLTYPE_EXPORT Q_DECL_EXPORT
#else
#define Q_QMLTYPE_EXPORT
#endif
Q_QMLTYPE_EXPORT void qml_register_types_target_sub()
{
    qmlRegisterModule("target.sub", 2, 0);
    qmlRegisterTypesAndRevisions<Obj>("target.sub", 2);
    qmlRegisterModule("target.sub", 2, 1);
}

static const QQmlModuleRegistration registration("target.sub", qml_register_types_target_sub);
