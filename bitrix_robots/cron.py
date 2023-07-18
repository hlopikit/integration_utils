from django.utils.module_loading import import_string

from settings import ilogger


def process_robot_requests(robot_cls, qs=None):
    if isinstance(robot_cls, str):
        robot_cls = import_string(robot_cls)

    portal_results = {}
    if qs is None:
        qs = robot_cls.objects.all()

    for robot in qs.filter(started__isnull=True).iterator():
        try:
            robot.start_process()
        except Exception as exc:
            ilogger.error(
                'process_robot_request_{}'.format(robot_cls.__class__.__name__),
                'robot {}: {}'.format(robot.id, exc),
            )

        portal = getattr(robot, 'portal', '')
        result = portal_results.setdefault(str(portal), dict(processed=0, errors=0, waiting=0))

        if robot.finished:
            if robot.is_success:
                result['processed'] += 1
            else:
                result['errors'] += 1
        else:
            result['waiting'] += 1

    return '\n\n'.join('{}\nprocessed: {}\nerrors: {}\nwaiting: {}'.format(
        portal, result['processed'], result['errors'], result['waiting']
    ) for portal, result in portal_results.items()).strip() or 'nothing to process'
