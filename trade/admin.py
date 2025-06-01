from django.contrib import admin
from .models import Coin, TradeLog, Candle_stick, Entry_point,Order_block

admin.site.register(Coin)
admin.site.register(TradeLog)
admin.site.register(Candle_stick)
admin.site.register(Entry_point)
admin.site.register(Order_block)