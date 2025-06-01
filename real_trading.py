import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coin_auto_trade.settings")

import django
django.setup()

from trade.models import Entry_point
from trade.utils import Trading, Position, API_keys, get_budget

import django
import asyncio
import websockets
import json
import time
from asgiref.sync import sync_to_async


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coin_auto_trade.settings")
django.setup()

API_KEY = os.environ['binance_api_key']
SECRET_KEY = os.environ['binance_secret_key']
keys = API_keys(API_KEY, SECRET_KEY)

triggered_entries = set()

@sync_to_async
def get_entry_points():
    return list(Entry_point.objects.all().order_by('tag'))

# 메인 로직
async def monitor_book_ticker():
    while True:
        await asyncio.sleep(1)
        
        entry_points = await get_entry_points()
        budget=get_budget(keys)
        if not entry_points:
            print("No entry points")
            await asyncio.sleep(1)
            continue

        symbols = [entry.tag.upper() for entry in entry_points]
        streams = [f"{symbol.lower() + 'usdt'}@bookTicker" for symbol in symbols]
        stream_url = "wss://fstream.binance.com/stream?streams=" + "/".join(streams)
        now = time.time()
        print(f"🔌 Connecting to: {stream_url}")
        trash = []
        stack = 0
        try:
            async with websockets.connect(
            stream_url,
            ping_interval=20,    
            ping_timeout=10      
            ) as ws:
                print("✅ WebSocket connected.")
                while True:
           

                    try:
                        exit_flag = 0
                        message = await ws.recv()
                        data = json.loads(message)
              
                        if 'data' not in data: continue
                        d = data['data']
                        symbol = d['s']              
                        bid = float(d['b'])          # 최우선 매수호가
                        ask = float(d['a'])          # 최우선 매도호가
                        current_entries = await get_entry_points()
                        if len(current_entries) > len(entry_points) or  time.time() - now > 600:
                            stack += 1
                            if stack > 50:
                                print('entry_point changed')
                                stack = 0
                                break
                        for entry in current_entries:
                            
                            entry_symbol = entry.tag.upper()
                            if not entry_symbol.endswith("USDT"):
                                entry_symbol += "USDT"
                            #print(entry_symbol,symbol)
                            if entry_symbol != symbol: continue
                            if entry.id in triggered_entries: continue
                            
                            if entry.direction == 'BUY':# and (ask - entry.entry_price)/entry.entry_price*100 < 1:
                                print(f"[{symbol}] ask={ask} entry={entry.entry_price} gap={round((ask - entry.entry_price)/entry.entry_price*100,2)}%")
                            if entry.direction == 'SELL':# and (entry.entry_price - bid)/bid*100 < 1:
                                print(f"[{symbol}] bid={bid} entry={entry.entry_price} gap={round((entry.entry_price - bid)/bid*100,2)}%")
                        
                            # 진입 조건 확인
                            if entry.direction == 'BUY' and ask <= entry.entry_price:
                                
                                print(f"🚀 BUY Triggered {symbol} at ask={ask}")
                            elif entry.direction == 'SELL' and bid >= entry.entry_price:
                                
                                print(f"🚀 SELL Triggered {symbol} at bid={bid}")
                            else:
                                continue

                            try:
                                
                                if budget > 5.0:
                                    target = Position( entry_symbol, entry.direction, entry.entry_price, entry.stop_loss, budget=budget)
                                    Trading(target, keys)
                                    print(f"✅ Order placed for {symbol}")
                                    budget = 0.0
                                else :
                                    print('already in-position')
                                    exit_flag = 1
                                

                            except Exception as e:
                                print(f"[ERROR] Trade failed for {symbol}: {e}")
                        if exit_flag == 1:
                            asyncio.sleep(1000)
                            break
                        
                    except Exception as e:
                        print(f"[MESSAGE ERROR] {e}")
                        
                        await asyncio.sleep(3)
                        break

        except Exception as e:
            print(f"[CONNECTION ERROR] {e}")
            await asyncio.sleep(5)
        

if __name__ == "__main__":
    asyncio.run(monitor_book_ticker())
