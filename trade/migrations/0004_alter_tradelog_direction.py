# Generated by Django 5.2 on 2025-04-27 09:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trade', '0003_remove_tradelog_exit_price'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tradelog',
            name='direction',
            field=models.CharField(max_length=10),
        ),
    ]
