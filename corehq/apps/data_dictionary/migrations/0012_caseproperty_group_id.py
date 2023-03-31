# Generated by Django 3.2.18 on 2023-03-31 12:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0011_casepropertygroup'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseproperty',
            name='group_id',
            field=models.ForeignKey(blank=True, db_column='group_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='properties', related_query_name='property', to='data_dictionary.casepropertygroup'),
        ),
    ]
