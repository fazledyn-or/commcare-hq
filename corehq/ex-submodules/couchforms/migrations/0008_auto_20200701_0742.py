# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-07-01 07:42
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('couchforms', '0007_auto_20191210_2206'),
    ]

    operations = [
        migrations.AlterField(
            model_name='unfinishedsubmissionstub',
            name='id',
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
    ]