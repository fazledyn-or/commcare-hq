# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-10-01 19:45
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models

from corehq.sql_db.operations import HqRunPython


def _product_type_to_is_product(apps, schema_editor):
    CreditLine = apps.get_model('accounting', 'CreditLine')
    assert {pt['product_type'] for pt in CreditLine.objects.values('product_type').distinct()} <= set(['', None])
    CreditLine.objects.filter(product_type__isnull=False).update(is_product=True)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0011_remove_softwareproduct'),
    ]

    operations = [
        migrations.AddField(
            model_name='creditline',
            name='is_product',
            field=models.BooleanField(default=False),
        ),
        HqRunPython(_product_type_to_is_product),
        migrations.RunSQL('SET CONSTRAINTS ALL IMMEDIATE',
                          reverse_sql=migrations.RunSQL.noop),
        migrations.RemoveField(
            model_name='creditline',
            name='product_type',
        ),
    ]
