# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-05-21 18:54
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bag_transfer', '0004_auto_20180518_1311'),
    ]

    operations = [
        migrations.AlterField(
            model_name='archives',
            name='created_time',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='archives',
            name='modified_time',
            field=models.DateTimeField(auto_now=True),
        ),
    ]