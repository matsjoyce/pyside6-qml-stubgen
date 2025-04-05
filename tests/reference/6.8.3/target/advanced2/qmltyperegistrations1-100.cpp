/****************************************************************************
** Generated QML type registration code
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <QtQml/qqml.h>
#include <QtQml/qqmlmoduleregistration.h>

#if __has_include(<in/advanced2.py>)
#  include <in/advanced2.py>
#endif


#if !defined(QT_STATIC)
#define Q_QMLTYPE_EXPORT Q_DECL_EXPORT
#else
#define Q_QMLTYPE_EXPORT
#endif
Q_QMLTYPE_EXPORT void qml_register_types_target_advanced2()
{
    qmlRegisterModule("target.advanced2", 1, 0);
    QT_WARNING_PUSH QT_WARNING_DISABLE_DEPRECATED
    qmlRegisterTypesAndRevisions<Layout2>("target.advanced2", 1);
    qmlRegisterTypesAndRevisions<LayoutAttached2>("target.advanced2", 1);
    QMetaType::fromType<LineEditorExtension2 *>().id();
    qmlRegisterTypesAndRevisions<LineEditorForeign2>("target.advanced2", 1);
    QT_WARNING_POP
    qmlRegisterModule("target.advanced2", 1, 100);
}

static const QQmlModuleRegistration targetadvanced2Registration("target.advanced2", qml_register_types_target_advanced2);
