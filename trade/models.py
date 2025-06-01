# models.py (Django ORM)

from django.db import models

class Coin(models.Model):
    tag = models.CharField(max_length=10) #'BTC'
    candle_size = models.CharField(max_length=10) #'15m'
    last_updated = models.DateTimeField(auto_now=True)

class TradeLog(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    direction = models.CharField(max_length=10)  # BUY or SELL
    entry_price = models.FloatField()
    stop_loss = models.FloatField()
    coin_tag = models.CharField(max_length=40)
    take_profit = models.FloatField()
    opened_at = models.FloatField()
    closed_at = models.FloatField(null=True, blank=True)
    log_type = models.CharField(max_length=40, default='back_testing')
    profit_loss = models.CharField(max_length=4,null=True, blank=True) #win or lose


class Candle_stick(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    open = models.FloatField()
    high = models.FloatField()
    low = models.FloatField()
    close = models.FloatField()
    open_time = models.FloatField()

class Order_block(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    open_time = models.FloatField()

    

class Entry_point(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    tag = models.CharField(max_length=40)
    direction = models.CharField(max_length=40) # BUY/SELL
    entry_price = models.FloatField()
    take_profit = models.FloatField()
    stop_loss = models.FloatField()