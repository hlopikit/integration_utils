# -*- coding: utf-8 -*-

from django.db import models


class KeyValue(models.Model):
    key = models.SlugField(u'ключ', primary_key=True)
    value = models.TextField(u'значение')
    comment = models.TextField(u'комментарий', blank=True)

    class Meta:
        app_label = 'app_settings'

    def __unicode__(self):
        return self.key
