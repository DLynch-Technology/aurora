# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-11-29 18:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bag_transfer', '0017_auto_20181129_1126'),
    ]

    operations = [
        migrations.AlterField(
            model_name='archives',
            name='machine_file_path',
            field=models.CharField(max_length=255),
        ),
    ]
