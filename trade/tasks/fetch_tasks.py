from celery import shared_task
from trade.utils import backtesting_and_find_entry, get_candle_data, orderblock,  get_server_time
from trade.models import Coin, TradeLog, Candle_stick, Entry_point, Order_block
import time


@shared_task
def fetch_coin():
    coin_list = ['BTC', 'ETH', 'XRP', 'SUI', 'BNB', 'EOS', 'BCH', 'LAYER', 'LTC', 'FARTCOIN', 'API3', 'TRUMP', 'LINK', 'AAVE', 'AUCTION', 'ZRO', 'SOL', 'NEO', 'WIF', 'BERA', 'CRV', 'TON', 'IP', 'MLN', 'ONDO', 'FIL', 'OP', 'NIL', 'DOT', 'TAO', 'KAITO', 'ORDI', 'ORCA', 'APT', 'ETC', 'FORM', 'W', 'AI16Z', 'ARB', 'RENDER', 'INJ', 'MKR', 'ATOM', 'EIGEN', 'ADA', 'ALGO', 'DYDX', 'OM', 'ENS', 'ZEN', 'BANANA', 'GRASS', 'AR', 'THE', 'VIRTUAL', 'PAXG', 'KAVA', 'AVAX', 'THETA']

    candle_sizes = ['5m','15m','1h']
    for tag in coin_list:
        for candle_size in candle_sizes:
            a,b=Coin.objects.get_or_create(
                    tag = tag,
                    candle_size = candle_size
                    )
            
@shared_task
def fetch_candle_data():
    coins = Coin.objects.all()
    for coin in coins:
        try:    

            candle_stick_filter = Candle_stick.objects.filter(coin=coin)
            if candle_stick_filter != None and len(candle_stick_filter) != 0:
                saved_past_prices = candle_stick_filter.order_by('open_time')
                num_candle = saved_past_prices.count()
                last_open_price = saved_past_prices.last().open_time
            else:
                saved_past_prices = None
                num_candle = 0
                last_open_price = 0
            now_ms = get_server_time()
            if coin.candle_size == '5m':
                minutes = 5
            elif coin.candle_size == '15m':
                minutes = 15
            elif coin.candle_size =='1h':
                minutes = 60
        
            if num_candle < 499:
                past_prices = get_candle_data(coin, 499)
            elif last_open_price < now_ms - 99 * 60000 * minutes: 
                past_prices = get_candle_data(coin, 499)
            else: 
                past_prices = get_candle_data(coin, 99)
            
            if past_prices is None:
                continue

            total_number = num_candle + len(past_prices)
            overed_number = 0 if total_number <= 499 else total_number - 500
            if saved_past_prices != None:
                candles_to_delete_ids = list(saved_past_prices[:overed_number].values_list('id', flat=True))
                Candle_stick.objects.filter(id__in=candles_to_delete_ids).delete()
                #Candle_stick.objects.filter(coin=coin).order_by('open_time').last().delete()
                candle_stick_filter = Candle_stick.objects.filter(coin=coin)
                existing = set(candle_stick_filter.values_list('open_time', flat=True))
            else:
                existing = []
            to_create = []
            for candle in past_prices:
                if candle['open_time'] not in existing:
                    to_create.append(Candle_stick(
                        coin=coin,
                        open=candle['open'],
                        high=candle['high'],
                        low=candle['low'],
                        close=candle['close'],
                        open_time=candle['open_time']
                    ))
            Candle_stick.objects.bulk_create(to_create)
            
        except Exception as e:
            print(f"[ERROR] {coin.tag}-{coin.candle_size} 캔들 데이터 확보 실패: {e}")

@shared_task
def back_testing_and_fetch_entry_point():
    new_entry_points = []
    coins = Coin.objects.all()
    for coin in coins:
        if coin.candle_size != '1h':
            try:
                new_entry = backtesting_and_find_entry(coin, 1)
                if new_entry != None:
                    new_entry_points.append(new_entry)
                
            except Exception as e:
                print(f"[ERROR] {coin.tag}-{coin.candle_size} 분석 실패: {e}")
    Entry_point.objects.all().delete()
    Entry_point.objects.bulk_create(new_entry_points)

    
@shared_task
def eraser():
    TradeLog.objects.all().delete()
    Order_block.objects.all().delete()
    