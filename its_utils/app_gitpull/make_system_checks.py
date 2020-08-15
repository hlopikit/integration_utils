from django.core.checks import Critical

from integration_utils.its_utils.app_gitpull import checks


def make_system_checks():
    messages = {}
    has_critical = False
    for d in dir(checks):
        if d.startswith('check_'):
            func = getattr(checks, d)
            if callable(func):
                result = func(None)
                for message in result:
                    critical = isinstance(message, Critical)
                    messages.setdefault(message.id, {
                        'critical': critical,
                        'messages': []
                    })['messages'].append(message.msg)
                    if critical:
                        has_critical = True

    # dict to sorted list of tuples
    return sorted([(k, v) for (k, v) in messages.items()], key=lambda m: not m[1]['critical']), has_critical
