# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-06-29 15:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bag_transfer', '0009_auto_20180627_1624'),
    ]

    operations = [
        migrations.AddField(
            model_name='archives',
            name='manifest',
            field=models.TextField(blank=True, null=True),
        ),
    ]
