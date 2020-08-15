# -*- coding: UTF-8 -*-
from django.core.checks import register, Critical


DEFAULT_DATABASE = 'default'


def get_unapplied_migrations(database=DEFAULT_DATABASE):
    from django.db import connections
    from django.db.migrations.executor import MigrationExecutor

    connection = connections[database]
    connection.prepare_database()
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()

    return executor.migration_plan(targets)


@register()
def check_unapplied_migrations(app_configs, **kwargs):
    errors = []
    migrations = get_unapplied_migrations()
    for migration, _ in migrations:
        errors.append(
            Critical(
                'migration {}.{} is not applied'.format(migration.app_label, migration.name),
                hint=None,
                obj='Critical',
                id='{}.W001'.format('unapplied_migrations'),
            )
        )

    return errors
