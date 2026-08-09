from django.db import models


class AbstractKeyValue(models.Model):
    """Abstract JSON key-value storage for an isolated Django application table.

    Concrete descendants receive their own table and Django model permissions.
    Use ``get_value()`` and ``set_value()`` rather than direct ORM calls so
    each application keeps one consistent persistence contract.
    """

    key = models.SlugField("ключ", primary_key=True)
    json_value = models.JSONField("json значение", null=True, blank=True)
    comment = models.TextField("комментарий", blank=True)

    migrate_legacy_values = False
    log_value = True

    class Meta:
        abstract = True

    def __str__(self):
        return self.key

    @classmethod
    def set_value(cls, key, value, comment=""):
        """Stores a JSON value through the concrete descendant model.

        Used by cron/helper code of the owning application. A descendant with
        sensitive values may set ``log_value = False`` to avoid logging JSON.
        """
        from settings import ilogger

        update_fields = {"json_value": value}
        if comment:
            update_fields["comment"] = comment
        result = cls.objects.filter(key=key).update(**update_fields)
        if not result:
            cls.objects.create(key=key, json_value=value, comment=comment)
        if cls.log_value:
            ilogger.debug("set_value", "{}->{}".format(key, value))
        else:
            ilogger.debug("set_value", "{} updated".format(key))

    @classmethod
    def get_value(cls, key, create=False, default="", comment=""):
        """Returns JSON value and optionally initializes it in the concrete model.

        ``KeyValue`` enables a one-time legacy migration; newly created
        application-specific descendants intentionally do not read the old global
        table unless they explicitly opt in.
        """
        try:
            return cls.objects.get(key=key).json_value
        except cls.DoesNotExist:
            if cls.migrate_legacy_values:
                legacy_value = cls._get_legacy_value(key)
                if legacy_value is not None:
                    cls.objects.create(key=key, json_value=legacy_value["value"], comment=legacy_value["comment"])
                    return legacy_value["value"]

            if create:
                cls.set_value(key=key, value=default, comment=comment)
                return default
            return None

    @staticmethod
    def _get_legacy_value(key):
        """Reads the previous global KeyValue table for the compatibility model only."""
        try:
            from integration_utils.its_utils.app_settings.models import KeyValue as LegacyKeyValue

            legacy_value = LegacyKeyValue.objects.get(key=key)
            return {"value": legacy_value.value, "comment": legacy_value.comment}
        except Exception:
            return None
