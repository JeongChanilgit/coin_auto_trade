# Generated by Django 5.2 on 2025-04-27 08:41

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('trade', '0002_alter_coin_log_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tradelog',
            name='exit_price',
        ),
    ]
