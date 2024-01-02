/****************************************************************************
** Generated QML type registration code
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <QtQml/qqml.h>
#include <QtQml/qqmlmoduleregistration.h>

#include <tests/target/advanced2.py>


#if !defined(QT_STATIC)
#define Q_QMLTYPE_EXPORT Q_DECL_EXPORT
#else
#define Q_QMLTYPE_EXPORT
#endif
Q_QMLTYPE_EXPORT void qml_register_types_target_advanced2()
{
    qmlRegisterModule("target.advanced2", 1, 0);
    qmlRegisterTypesAndRevisions<Layout2>("target.advanced2", 1);
    qmlRegisterTypesAndRevisions<LayoutAttached2>("target.advanced2", 1);
    QMetaType::fromType<LineEditorExtension2 *>().id();
    qmlRegisterTypesAndRevisions<LineEditorForeign2>("target.advanced2", 1);
    qmlRegisterModule("target.advanced2", 1, 100);
}

static const QQmlModuleRegistration registration("target.advanced2", qml_register_types_target_advanced2);
