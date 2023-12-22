/****************************************************************************
** Generated QML type registration code
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <QtQml/qqml.h>
#include <QtQml/qqmlmoduleregistration.h>

#include <tests/target/clses.py>
#include <tests/target/clses2.py>


#if !defined(QT_STATIC)
#define Q_QMLTYPE_EXPORT Q_DECL_EXPORT
#else
#define Q_QMLTYPE_EXPORT
#endif
Q_QMLTYPE_EXPORT void qml_register_types_target()
{
    qmlRegisterTypesAndRevisions<Anonymous>("target", 1);
    qmlRegisterTypesAndRevisions<Named>("target", 1);
    qmlRegisterTypesAndRevisions<Named2>("target", 1);
    qmlRegisterTypesAndRevisions<Normal>("target", 1);
    QMetaType::fromType<QStandardItemModel *>().id();
    qmlRegisterTypesAndRevisions<SignalsAndProperties>("target", 1);
    qmlRegisterAnonymousType<QAbstractItemModel, 254>("target", 1);
    qmlRegisterTypesAndRevisions<Singleton>("target", 1);
    qmlRegisterTypesAndRevisions<Singleton2>("target", 1);
    qmlRegisterTypesAndRevisions<Singleton3>("target", 1);
    qmlRegisterTypesAndRevisions<Uncreatable>("target", 1);
    qmlRegisterTypesAndRevisions<UncreatableWithReason>("target", 1);
    qmlRegisterTypesAndRevisions<UncreatableWithReason2>("target", 1);
    qmlRegisterModule("target", 1, 0);
}

static const QQmlModuleRegistration registration("target", qml_register_types_target);
