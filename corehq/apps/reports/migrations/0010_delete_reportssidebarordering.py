# Generated by Django 3.2.14 on 2022-08-29 14:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0009_remove_tableauserver_domain_username'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ReportsSidebarOrdering',
        ),
    ]
