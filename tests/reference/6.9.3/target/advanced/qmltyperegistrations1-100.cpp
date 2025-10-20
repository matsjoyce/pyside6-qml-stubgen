/****************************************************************************
** Generated QML type registration code
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <QtQml/qqml.h>
#include <QtQml/qqmlmoduleregistration.h>

#if __has_include(<in/advanced.py>)
#  include <in/advanced.py>
#endif


#if !defined(QT_STATIC)
#define Q_QMLTYPE_EXPORT Q_DECL_EXPORT
#else
#define Q_QMLTYPE_EXPORT
#endif
Q_QMLTYPE_EXPORT void qml_register_types_target_advanced()
{
    qmlRegisterModule("target.advanced", 1, 0);
    QT_WARNING_PUSH QT_WARNING_DISABLE_DEPRECATED
    qmlRegisterTypesAndRevisions<Layout>("target.advanced", 1);
    qmlRegisterTypesAndRevisions<LayoutAttached>("target.advanced", 1);
    QMetaType::fromType<LineEditorExtension *>().id();
    qmlRegisterTypesAndRevisions<LineEditorForeign>("target.advanced", 1);
    QT_WARNING_POP
    qmlRegisterModule("target.advanced", 1, 100);
}

static const QQmlModuleRegistration targetadvancedRegistration("target.advanced", qml_register_types_target_advanced);
