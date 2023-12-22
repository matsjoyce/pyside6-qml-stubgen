/****************************************************************************
** Generated QML type registration code
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <QtQml/qqml.h>
#include <QtQml/qqmlmoduleregistration.h>

#include <tests/target/advanced.py>


#if !defined(QT_STATIC)
#define Q_QMLTYPE_EXPORT Q_DECL_EXPORT
#else
#define Q_QMLTYPE_EXPORT
#endif
Q_QMLTYPE_EXPORT void qml_register_types_target_advanced()
{
    qmlRegisterModule("target.advanced", 1, 0);
    qmlRegisterTypesAndRevisions<Layout>("target.advanced", 1);
    qmlRegisterTypesAndRevisions<LayoutAttached>("target.advanced", 1);
    QMetaType::fromType<LineEditorExtension *>().id();
    qmlRegisterTypesAndRevisions<LineEditorForeign>("target.advanced", 1);
    qmlRegisterModule("target.advanced", 1, 100);
}

static const QQmlModuleRegistration registration("target.advanced", qml_register_types_target_advanced);
