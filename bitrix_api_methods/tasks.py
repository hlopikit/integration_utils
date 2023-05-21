
def add_param(obj, key, value):
    if value:
        obj[key] = value
    return obj

def add_param_yesno(obj, key, value):
    value = "Y" if value else "N"
    return add_param(obj, key, value)
"""
STATUS: 2 - Ждет выполнения, 3 - Выполняется, 4 - Ожидает контроля, 5 - Завершена, 6 - Отложена. По умолчанию - 2
PRIORITY: 2 - Высокий, 1 - Средний, 0 - Низкий. По умолчанию - 1
"""

def tasks_task_update(but, task_id, title=None, description=None, responsible_id=None, group_id=None, status=None, allow_change_deadline: bool=None, need_result: bool=None):
    # https://dev.1c-bitrix.ru/rest_help/tasks/task/tasks/tasks_task_update.php

    fields = {}
    method = "tasks.task.update"
    params = {"task_id": task_id, "fields": fields}

    add_param(fields, "TITLE", title)
    add_param(fields, "DESCRIPTION", description)
    add_param(fields, "RESPONSIBLE_ID", responsible_id)
    add_param(fields, "GROUP_ID", group_id)
    add_param(fields, "STATUS", status)
    add_param_yesno(fields, "ALLOW_CHANGE_DEADLINE", allow_change_deadline)

    # Дикие параметры
    if need_result:
        fields['SE_PARAMETER'] = [{'VALUE': 'Y', 'CODE': 3 }]


    result = but.call_api_method(method, params)


    return result