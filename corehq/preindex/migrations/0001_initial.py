# Generated by Django 3.2.16 on 2023-01-25 22:38

import corehq.preindex.django_migrations
from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('es', '0001_bootstrap_es_indexes'),
    ]

    operations = [
        corehq.preindex.django_migrations.RequestReindex(
        ),
    ]