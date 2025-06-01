import requests
import hmac
import hashlib
import time

import csv
import math
import pandas as pd
import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
from trade.models import Coin, TradeLog,Candle_stick,Entry_point,Order_block
from django.utils import timezone

class API_keys:
    def __init__(self,api_key,secret_key):
        self.api_key = api_key
        self.secret_key = secret_key

class Position:
    def __init__( self, name, order_direction, entry_price = None, stop_loss = None, budget = None, demand_low = None, demand_high = None, supply_low = None, supply_high = None, earn_rate = 1):

        self.order_direction = order_direction.upper()
        self.tag = name.upper()
        tick_size, step_size = get_coin_info(self.tag)
        self.order_block = orderblock(demand_low, demand_high, supply_low, supply_high)

        if entry_price != None:
            
            tick_demical_part = 0
            for i in range(len(str(tick_size))):
                if str(tick_size)[i] == '.':
                    tick_demical_part = len(str(tick_size)) - i - 1
            
            step_demical_part = 0
            for i in range(len(str(step_size))):
                if str(step_size)[i] == '.':
                    step_demical_part = len(str(step_size)) - i - 1

            self.entry_price = round(entry_price,tick_demical_part)
            buffered_stop_loss = stop_loss + tick_size if order_direction == "SELL" else stop_loss - tick_size
            self.stop_loss = round(buffered_stop_loss,tick_demical_part)
            self.take_profit = round(entry_price + earn_rate * (entry_price - stop_loss),tick_demical_part)
            
            self.leverage = int(min(4, max(1 ,4 // abs((100 * (self.entry_price - self.stop_loss) / self.entry_price)))))
            self.amount = round(budget / self.entry_price * self.leverage, step_demical_part)
            
        

class orderblock:
   def __init__(self, demand_low, demand_high, supply_low, supply_high, inefficiency = False, unmitigated = True):
      self.supply = { "high": supply_high, "low": supply_low, 'inefficiency' : inefficiency, 'unmitigated' : unmitigated, 'open_time': 0}
      self.demand = { "high": demand_high, "low": demand_low, 'inefficiency' : inefficiency, 'unmitigated' : unmitigated, 'open_time': 0}

def get_coin_info(symbol):

    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    response = requests.get(url).json()
    tick_size = None
    step_size = None
    for s in response["symbols"]:
        if s["symbol"] == symbol:
            for f in s["filters"]:
                if f["filterType"] == "PRICE_FILTER":
                    tick_size = f["tickSize"]
                if f["filterType"] == "LOT_SIZE":
                    step_size = f["stepSize"]
            
    return float(tick_size), float(step_size) 

def get_server_time():
    response = requests.get("https://api.binance.com/api/v3/time")
   
    server_time =  response.json()["serverTime"]
    local_time = int(time.time() * 1000)
    time_offset = server_time - local_time 
    return int(time.time() * 1000) + time_offset

def generate_signature(params, secret_key):
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return hmac.new(secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()


def set_leverage(position, keys):
    url = "https://fapi.binance.com/fapi/v1/leverage"
    API_KEY = keys.api_key
    SECRET_KEY = keys.secret_key

    params = {
        "symbol": position.tag,

        "leverage": position.leverage,

        "timestamp": get_server_time()
    }
    params["signature"] = generate_signature(params, SECRET_KEY)
    headers = {"X-MBX-APIKEY": API_KEY}
    requests.post(url, headers=headers, params=params).json()


def close_price( position):
    url = "https://fapi.binance.com/fapi/v1/klines"
    headers = {"accept": "application/json"}
    params = {
        "symbol" : position.tag,

        "interval" : '5m',

        "limit" : 1
        }
    close_price = float(requests.get(url,params=params,headers=headers).json()[0][4]) # close price
    
    return close_price


def set_limit_order( position, keys): #sl이 설정된 주문 넣음
    url = "https://fapi.binance.com/fapi/v1/order"
    API_KEY = keys.api_key
    SECRET_KEY = keys.secret_key
    headers = {
        "accept" : "application/json",
        "X-MBX-APIKEY": API_KEY
    }
    params = {
        "symbol" : position.tag,
        "side" : position.order_direction,  # "BUY"  또는 "SELL" 
        "type" : "LIMIT",
        "quantity" : position.amount,
        "timestamp" : get_server_time(),
        'timeInForce' : "GTC",
        "price" : position.entry_price
    }
    #print(position.amount)
    params["signature"] = generate_signature(params, SECRET_KEY)
    response = requests.post(url, headers=headers, params=params).json()
    print(response)
    #position.amount = float(response["executedQty"])    


def set_take_profit( position, keys): #TP포지션을 지정가로 넣음
    url = "https://fapi.binance.com/fapi/v1/order"
    headers = {"X-MBX-APIKEY": keys.api_key}
    close_direction = "SELL" if position.order_direction == "BUY" else "BUY"

    params = {
        "symbol": position.tag,
        "side": close_direction,  # 포지션 반대 방향
        "type": "TAKE_PROFIT",  # 지정가 TP 주문
        "quantity": position.amount,
        "timestamp": get_server_time(),
        'reduceOnly': True,
        "stopPrice": position.take_profit,  # 트리거 가격
        "price": position.take_profit,  # 실행될 지정가
        "timeInForce": "GTC",  # 주문 유지 방식 (Good-Till-Canceled)
    }

    params["signature"] = generate_signature(params, keys.secret_key)
    print(requests.post(url, headers=headers, params=params).json())


def set_stop_loss( position, keys): #SL포지션을 시장가로 넣음
    url = "https://fapi.binance.com/fapi/v1/order"
    API_KEY = keys.api_key
    SECRET_KEY = keys.secret_key
    headers = {
        "accept" : "application/json",
        "X-MBX-APIKEY": API_KEY
    }

    #포지션 정리하는 방향
    close_direction = "SELL" if position.order_direction == "BUY" else "BUY"


    params = {
        "symbol" : position.tag,
        "side" : close_direction,  # "BUY"  또는 "SELL" 
        "type" : "STOP_MARKET",
        "quantity" : position.amount,
        "timestamp" : get_server_time(),

        'reduceOnly': True,
        "stopPrice" : position.stop_loss
    }
    params["signature"] = generate_signature(params, SECRET_KEY)
    print(requests.post(url, headers=headers, params=params).json())


def Trading( position, keys): #주문 총괄
    set_leverage( position, keys)
    set_limit_order( position, keys)
    set_stop_loss( position, keys)
    set_take_profit( position, keys)


def get_budget(keys):
    url = "https://fapi.binance.com/fapi/v3/balance"
    API_KEY = keys.api_key
    SECRET_KEY = keys.secret_key
    headers = {
        "accept" : "application/json",
        "X-MBX-APIKEY": API_KEY
    }
    params = {
        "timestamp" : get_server_time(),
        }
    params["signature"] = generate_signature(params, SECRET_KEY)
    response = requests.get(url, headers=headers, params=params).json()
    for res in response:
        if res['asset'] == "USDT":
            #print(res)
            #print(round(float(res['availableBalance']),2) - 0.5)
            return round(float(res['availableBalance']),2) - 0.5
    return 0
                                   


def printing(position):
    print("simbol :", position.tag)
    print("direction :", position.leverage, "X", position.order_direction)
    print("entry_price / amount :", position.entry_price, position.amount)
    print("TP / SL :", position.take_profit, "/", position.stop_loss)

def entry_logic(coin, trend, candle, orderblocks, earn_rate, past_prices, real_trading = False):
    tag, candle_size = coin.tag, coin.candle_size
    if candle_size == '15m':
        high_scale_candle_size = '1h'
    elif candle_size == '5m':
        high_scale_candle_size = '15m'
    elif candle_size =='3m':
        high_scale_candle_size = '15m'
    elif candle_size =='30m':
        high_scale_candle_size = '2h'


    #상승 추세일 때 
    if trend == 'increasing':

        #현 캔들의 시가가 수요 오더블록보다 높았을 때
        if candle.open > orderblocks.demand['high']:
            
            #현 캔들의 저가가 수요 오더블록 안에 들었을 때 (계산 때에는 오더블록을 넘어서는 경우도 반영되어야함)
            if candle.low <= orderblocks.demand['high'] or real_trading:
                
                #오더블록의 길이가 0.5퍼센트 이상일 때
                if (orderblocks.demand['high'] - orderblocks.demand['low']) /orderblocks.demand['low'] > 0.005:
                    
                    #오더블록에 inefficiency가 있을 때
                    if orderblocks.demand['inefficiency'] == True:

                        #오더블록이 unmitigated 상태일 때
                        if is_unmitigated(past_prices, orderblocks, candle, trend):             

                            high_scale_coin = Coin.objects.get(tag = tag, candle_size = high_scale_candle_size)
                            high_scale_trend, high_scale_ob = high_scale_analyze(high_scale_coin, candle.open_time)
                            
                            #큰 타임스케일에서의 트렌드와 동일할 때
                            if high_scale_trend == trend:# >= htf['orderblock'].demand['low']:
    
                                long = {'signal': 1,'side':'BUY', 'entry': orderblocks.demand['high'], 'stop_loss' : orderblocks.demand['low']}
                                long['take_profit'] = long['entry'] + earn_rate * (long['entry'] - long['stop_loss'])
                                return long

                               
    #하락 추세일 때 
    elif trend == 'decreasing':

        #현 캔들의 시가가 공급 오더블록보다 낮았을 때
        if candle.open < orderblocks.supply['low']:
            
            #현 캔들의 고가가 공급 오더블록 안에 들었을 때
            if orderblocks.supply['low'] <= candle.high or real_trading:
                
                #오더블록의 길이가 0.5퍼센트 이상일 때
                if (orderblocks.supply['high'] - orderblocks.supply['low'])/orderblocks.supply['low'] > 0.005:

                    #오더블록에 inefficiency가 있을 때
                        if orderblocks.supply['inefficiency'] == True:

                            #오더블록이 unmitigated 상태일 때
                            if is_unmitigated(past_prices, orderblocks, candle, trend):

                                high_scale_coin = Coin.objects.get(tag = tag, candle_size = high_scale_candle_size)
                                high_scale_trend, high_scale_ob = high_scale_analyze(high_scale_coin, candle.open_time)
                                
                                #큰 타임스케일에서의 트렌드와 동일할 때
                                if high_scale_trend == trend:# <= htf['orderblock'].supply['high']:

                                    short = {'signal': 1,'side':'SELL','entry': orderblocks.supply['low'], 'stop_loss' : orderblocks.supply['high']}
                                    short['take_profit'] = short['entry'] + earn_rate * (short['entry'] - short['stop_loss'])
                                    return short
   
    return {'signal' : 0}

def entry_logic_save(coin, trend, candle, orderblocks, earn_rate, past_prices, real_trading = False):
    tag, candle_size = coin.tag, coin.candle_size
    if candle_size == '15m':
        high_scale_candle_size = '1h'
    elif candle_size == '5m':
        high_scale_candle_size = '15m'
    elif candle_size =='3m':
        high_scale_candle_size = '15m'
    elif candle_size =='30m':
        high_scale_candle_size = '2h'


    #상승 추세일 때 
    if trend == 'increasing':

        #현 캔들의 시가가 수요 오더블록보다 높았을 때
        if candle.open > orderblocks.demand['high']:
            
            #현 캔들의 저가가 수요 오더블록 안에 들었을 때 (계산 때에는 오더블록을 넘어서는 경우도 반영되어야함)
            if candle.low <= orderblocks.demand['high'] or real_trading:
                
                #오더블록의 길이가 0.5퍼센트 이상일 때
                if (orderblocks.demand['high'] - orderblocks.demand['low']) /orderblocks.demand['low'] > 0.005:
                    
                    #오더블록에 inefficiency가 있을 때
                    if orderblocks.demand['inefficiency'] == True:

                        #오더블록이 unmitigated 상태일 때
                        if is_unmitigated(past_prices, orderblocks, candle, trend):             

                            high_scale_coin = Coin.objects.get(tag = tag, candle_size = high_scale_candle_size)
                            high_scale_trend, high_scale_ob = high_scale_analyze(high_scale_coin, candle.open_time)
                            long = {'signal': 1,'side':'BUY', 'entry': orderblocks.demand['high'], 'stop_loss' : orderblocks.demand['low']}
                            long['take_profit'] = long['entry'] + earn_rate * (long['entry'] - long['stop_loss'])
                            #큰 타임스케일에서의 트렌드와 동일할 때
                            if high_scale_trend == trend:# >= htf['orderblock'].demand['low']:
    
                                return long

                               
    #하락 추세일 때 
    elif trend == 'decreasing':

        #현 캔들의 시가가 공급 오더블록보다 낮았을 때
        if candle.open < orderblocks.supply['low']:
            
            #현 캔들의 고가가 공급 오더블록 안에 들었을 때
            if orderblocks.supply['low'] <= candle.high or real_trading:
                
                #오더블록의 길이가 0.5퍼센트 이상일 때
                if (orderblocks.supply['high'] - orderblocks.supply['low'])/orderblocks.supply['low'] > 0.005:

                    #오더블록에 inefficiency가 있을 때
                        if orderblocks.supply['inefficiency'] == True:

                            #오더블록이 unmitigated 상태일 때
                            if is_unmitigated(past_prices, orderblocks, candle, trend):

                                high_scale_coin = Coin.objects.get(tag = tag, candle_size = high_scale_candle_size)
                                high_scale_trend, high_scale_ob = high_scale_analyze(high_scale_coin, candle.open_time)
                                
                                #큰 타임스케일에서의 트렌드와 동일할 때
                                if high_scale_trend == trend:# <= htf['orderblock'].supply['high']:

                                    short = {'signal': 1,'side':'SELL','entry': orderblocks.supply['low'], 'stop_loss' : orderblocks.supply['high']}
                                    short['take_profit'] = short['entry'] + earn_rate * (short['entry'] - short['stop_loss'])
                                    return short
   
    return {'signal' : 0}


def is_unmitigated(past_prices, orderblocks, candle, trend):
    if trend == 'increasing':

        ob = orderblocks.demand
        for price in past_prices:

            # 오더블록이 생성 된 시점과 현 캔들의 시점 사이에 가격이 수요 오더블록에 닿았을 때
            if ob['renewal_time'] < price.open_time < candle.open_time:
                if price.low <= ob['high']:
                    return False

            # 한번도 닿지 않고 현 캔들에 도착했을 때
            elif price.open_time >= candle.open_time:
                return True 


    elif trend == 'decreasing':

        ob = orderblocks.supply
        for price in past_prices:
            
            # 오더블록이 생성 된 시점과 현 캔들의 시점 사이에 가격이 공급 오더블록에 닿았을 때
            if ob['renewal_time'] < price.open_time < candle.open_time:

                if price.high >= ob['low']:
                    return False

            # 한번도 닿지 않고 현 캔들에 도착했을 때
            elif price.open_time >= candle.open_time:
                return True 




def trade_simulator(coin, candle, entry_analsis,price):
    tag, candle_size = coin.tag, coin.candle_size
    
    entry_price, stop_loss, take_profit = entry_analsis['entry'], entry_analsis['stop_loss'], entry_analsis['take_profit']
    time_gap = 1000 * int(candle_size[:-1]) * 60
    data = get_candle_data(coin, 99, start_time = candle.open_time,extra_candle_size='1m')
    exit_time = candle.open_time


    if data == None or len(data) < 10:
            coin.delete()
            return {'outcome': '보합'} 
    
    if stop_loss < take_profit: #long
        for i in range(len(data)):
            if data[i]['open_time'] > exit_time + time_gap:
                exit_time += time_gap

            if data[i]['low'] <= stop_loss:
                
                return {'entry_price': entry_price, 'stop_loss': stop_loss, 'take_profit': take_profit, 'direction':'BUY', 'exit_price':stop_loss, 'outcome': 'lose','side':'long', 'entry_time' : candle.open_time, 'exit_time': exit_time, 'open_time':candle.open_time}
            
            elif data[i]['high'] >= take_profit and data[i]['close'] > data[i]['open']:
                return {'entry_price': entry_price, 'stop_loss': stop_loss, 'take_profit': take_profit, 'direction':'BUY', 'exit_price':take_profit, 'outcome': 'win','side':'long', 'entry_time' : candle.open_time, 'exit_time': exit_time, 'open_time':candle.open_time}

    elif entry_analsis['stop_loss'] > entry_analsis['take_profit']: #short
        for i in range(len(data)):
            if data[i]['open_time'] > exit_time + time_gap:
                exit_time += time_gap

            if data[i]['high'] >= stop_loss:
                return {'entry_price': entry_price, 'stop_loss': stop_loss, 'take_profit': take_profit, 'direction':'SELL', 'exit_price':stop_loss, 'outcome': 'lose','side':'short', 'entry_time' : candle.open_time, 'exit_time': exit_time, 'open_time':candle.open_time}
            
            elif data[i]['low'] <= take_profit and data[i]['open'] > data[i]['close']:
                return {'entry_price': entry_price, 'stop_loss': stop_loss, 'take_profit': take_profit, 'direction':'SELL', 'exit_price':take_profit, 'outcome': 'win','side':'short', 'entry_time' : candle.open_time, 'exit_time': exit_time, 'open_time':candle.open_time}
            
    return {'outcome': '보합'}


def trade_simulator_past(coin, candle, entry_analsis, prices):
    tag, candle_size = coin.tag, coin.candle_size
    
    entry_price, stop_loss, take_profit = entry_analsis['entry'], entry_analsis['stop_loss'], entry_analsis['take_profit']

    after_prices = []
    for price in prices:
        if price.open_time >= candle.open_time:
            after_prices.append(price)


    if after_prices == None or len(after_prices) < 10:
            coin.delete()
            return {'outcome': '보합'} 
    
    if stop_loss < take_profit: #long
        for price in after_prices:

            exit_time = price.open_time

            #저가가 손절가보다 낮을 때 -> 손절
            if price.low <= stop_loss:                
                return {'entry_price': entry_price, 'stop_loss': stop_loss, 'take_profit': take_profit, 'direction':'BUY', 'exit_price':stop_loss, 'outcome': 'lose','side':'long', 'entry_time' : candle.open_time, 'exit_time': exit_time, 'open_time':candle.open_time}
            
            #고가가 익절가보다 높고, *포지션 진입 캔들 이후의 캔들일 때* -> 익절
            elif price.high >= take_profit and price.open_time > candle.open_time:
                return {'entry_price': entry_price, 'stop_loss': stop_loss, 'take_profit': take_profit, 'direction':'BUY', 'exit_price':take_profit, 'outcome': 'win','side':'long', 'entry_time' : candle.open_time, 'exit_time': exit_time, 'open_time':candle.open_time}

            #종가가 익절가보다 높을 때 *이때는 포지션 진입 캔들도 익절구간임* -> 익절
            elif price.close >= take_profit:
                return {'entry_price': entry_price, 'stop_loss': stop_loss, 'take_profit': take_profit, 'direction':'BUY', 'exit_price':take_profit, 'outcome': 'win','side':'long', 'entry_time' : candle.open_time, 'exit_time': exit_time, 'open_time':candle.open_time}

    elif stop_loss > take_profit: #short
        for price in after_prices:

            exit_time = price.open_time

            #고가가 손절가보다 높을 때 -> 손절
            if price.high >= stop_loss:                
                return {'entry_price': entry_price, 'stop_loss': stop_loss, 'take_profit': take_profit, 'direction':'SELL', 'exit_price':stop_loss, 'outcome': 'lose','side':'short', 'entry_time' : candle.open_time, 'exit_time': exit_time, 'open_time':candle.open_time}
            
            #저가가 익절가보다 낮고, *포지션 진입 캔들 이후의 캔들일 때* -> 익절
            elif price.low <= take_profit and price.open_time > candle.open_time:
                return {'entry_price': entry_price, 'stop_loss': stop_loss, 'take_profit': take_profit, 'direction':'SELL', 'exit_price':take_profit, 'outcome': 'win','side':'short', 'entry_time' : candle.open_time, 'exit_time': exit_time, 'open_time':candle.open_time}

            #종가가 익절가보다 낮을 때 *이때는 포지션 진입 캔들도 익절구간임* -> 익절
            elif price.close <= take_profit:
                return {'entry_price': entry_price, 'stop_loss': stop_loss, 'take_profit': take_profit, 'direction':'SELL', 'exit_price':take_profit, 'outcome': 'win','side':'short', 'entry_time' : candle.open_time, 'exit_time': exit_time, 'open_time':candle.open_time}

        
    return {'outcome': '보합'} 



def get_candle_data(coin, length, start_time = None, extra_candle_size = None):
    tag, candle_size = coin.tag, coin.candle_size
    if extra_candle_size != None:
        candle_size = extra_candle_size
    symbol = tag + 'USDT'
    url = "https://fapi.binance.com/fapi/v1/klines"
    headers = {"accept": "application/json"}
    if start_time == None:
        params = {
            "symbol" : symbol,

            "interval" : candle_size,

            "limit" : length
        }
    else:
        start_time = int(start_time)
        params = {
            "symbol" : symbol,

            "interval" : candle_size,

            "limit" : length,

            "startTime" : start_time
        }

    if length < 100:
        weight = 1
    elif length < 500:
        weight = 2
    elif length < 1000:
        weight = 5
    else:
        weight = 10
    
    sleep_time = round(1.3 * weight / (2000 / 60),2)
    time.sleep(sleep_time)
    response = requests.get(url,params=params,headers=headers)
    m_weight = int(response.headers.get("X-MBX-USED-WEIGHT-1M", 0))
    if m_weight > 2300:
        time.sleep(120)

    past_prices = response.json()
    if past_prices == None or len(past_prices) < 10:
        return None
    for i in range(len(past_prices)):
        prices = past_prices[i]
        candle_data = {'open' : float(prices[1]), 'high' : float(prices[2]), 'low' : float(prices[3]), 'close' : float(prices[4]), 'open_time' : float(prices[0])}
        past_prices[i] = candle_data

    return past_prices



def write_log(coin,result,log_type):

    if log_type == 'back_testing':
        trade,_ = TradeLog.objects.get_or_create(
            coin=coin,
            coin_tag=coin.tag,
            direction=result['direction'],
            entry_price=result['entry_price'],
            stop_loss=result['stop_loss'],
            take_profit=result['take_profit'],
            opened_at=result['entry_time'],
            closed_at=result['exit_time'],
            profit_loss=result['outcome'],
            log_type=log_type
        )
        
    elif log_type == 'real_trading':
        trade, created = TradeLog.objects.get_or_create(
            coin=coin,
            coin_tag=coin.tag,
            direction=result['direction'],
            entry_price=result['entry_price'],
            stop_loss=result['stop_loss'],
            take_profit=result['take_profit'],
            opened_at=result['entry_time'],
            log_type=log_type
        )
        if created == False:
            trade.closed_at = result['exit_time']
            trade.profit_loss = result['outcome']
            trade.save()






def backtesting_and_find_entry(coin, earn_rate):
    #initial_setting----------------------------------------------------------------------------------------------------------
    past_prices = Candle_stick.objects.filter(coin=coin).order_by('open_time')

    current_orderblock = orderblock(past_prices[0].high,past_prices[0].low,past_prices[0].high,past_prices[0].low)
    temp_high = 0
    temp_low = 1000000000
    trend = 'increasing' if past_prices[0].close >= past_prices[0].open else 'decreasing'
    #initial_setting----------------------------------------------------------------------------------------------------------



    for i in range(len(past_prices)):

        candle = past_prices[i]
        entry_analysis = entry_logic(coin, trend, candle, current_orderblock, earn_rate, past_prices)
        if entry_analysis['signal']:
            result = trade_simulator(coin, candle, entry_analysis,past_prices)
   
            if result['outcome'] != '보합':
                write_log(coin, result,'back_testing')
        if i == len(past_prices)-1:
            entry_analysis = entry_logic(coin, trend, candle, current_orderblock, earn_rate, past_prices, real_trading=True)
            return make_entry_point(coin, entry_analysis)
        
        #상방 bos
        if temp_high < candle.high and trend != 'decreasing':
            
            for j in reversed(range(i)):
                cur_candle = past_prices[j]

                if cur_candle.high == temp_high:
                    if j + 4 <= i: #전 고점 좌표 찾기.
                        demand_high = min(past_prices[j:i], key = lambda x : x.high).high
                        demand_low = min(past_prices[j:i], key = lambda x : x.low).low
                        current_orderblock.demand = { "high": demand_high, "low": demand_low, 'inefficiency' : False, 'unmitigated': True,'open_time':min(past_prices[j:i], key = lambda x : x.low).open_time, 'renewal_time' : candle.open_time}
                        
                        Order_block.objects.get_or_create(coin=coin,open_time=current_orderblock.demand['open_time'])
                        bos = 1

                        for k in range(j,i+1):
                            if k > 0 and len(past_prices)-1 > k:

                                if (past_prices[k+1].low - past_prices[k-1].high)/past_prices[k-1].high > 0.004:
                                    current_orderblock.demand['inefficiency'] = True
                    break
                    
            trend = 'increasing'
        #하방 bos
        
        elif temp_low > candle.low and trend != 'increasing':
 
            for j in reversed(range(i)):

                cur_candle = past_prices[j]

                if cur_candle.low == temp_low :
                    if j + 4 <= i: #전 저점 좌표 찾기.
                        supply_high = max(past_prices[j:i], key = lambda x : x.high).high
                        supply_low = max(past_prices[j:i], key = lambda x : x.low).low
                        current_orderblock.supply = { "high": supply_high, "low": supply_low, 'inefficiency' : False, 'unmitigated': True,'open_time':max(past_prices[j:i], key = lambda x : x.high).open_time, 'renewal_time' : candle.open_time}
                       
                        Order_block.objects.get_or_create(coin=coin,open_time=current_orderblock.supply['open_time'])
                        bos = 1

                        for k in range(j,i+1):
                            if k > 0 and len(past_prices)-1 > k:
                                if (past_prices[k-1].low - past_prices[k+1].high)/past_prices[k+1].high > 0.004:

                                            current_orderblock.supply['inefficiency'] = True
                    break       
                        
                    
                trend = 'decreasing'

        #상방에서 하방 choch
        elif current_orderblock.demand['low'] > candle.close and trend != 'decreasing':

            for j in reversed(range(i)):
                cur_candle = past_prices[j]
              
                if cur_candle.low == current_orderblock.demand['low']: #마지막 bos가 일어난 상방 오더블록 찾기
                    supply_high = max(past_prices[j:i], key = lambda x : x.high).high
                    supply_low = max(past_prices[j:i], key = lambda x : x.low).low
                    current_orderblock.supply = { "high": supply_high, "low": supply_low, 'inefficiency' : False, 'unmitigated': True,'open_time':max(past_prices[j:i], key = lambda x : x.high).open_time, 'renewal_time' : candle.open_time}
                    
                    Order_block.objects.get_or_create(coin=coin,open_time=current_orderblock.supply['open_time'])
                    for k in range(j,i+1):
                        if k > 0 and len(past_prices)-1 > k:
                            if (past_prices[k-1].low - past_prices[k+1].high)/past_prices[k+1].high > 0.004:

                                        current_orderblock.supply['inefficiency'] = True
                    bos = 0
                    break
               
            trend = 'decreasing'
            temp_low = candle.low


        #하방에서 상방 choch
        elif current_orderblock.supply['high'] < candle.close and trend != 'increasing':

            for j in reversed(range(i)):
                cur_candle = past_prices[j]

                if cur_candle.high == current_orderblock.supply['high']:  #마지막 bos가 일어난 히방 오더블록 찾기
                    demand_high = min(past_prices[j:i], key = lambda x : x.high).high
                    demand_low = min(past_prices[j:i], key = lambda x : x.low).low
                    current_orderblock.demand = { "high": demand_high, "low": demand_low, 'inefficiency' : False, 'unmitigated': True,'open_time':min(past_prices[j:i], key = lambda x : x.low).open_time, 'renewal_time' : candle.open_time}
                    
                    Order_block.objects.get_or_create(coin=coin,open_time = current_orderblock.demand['open_time'])
                    for k in range(j,i+1):
                        if k > 0 and len(past_prices)-1 > k:

                            if (past_prices[k+1].low - past_prices[k-1].high)/past_prices[k-1].high > 0.004:
                                current_orderblock.demand['inefficiency'] = True
                    bos = 0
                    break
        
            trend = 'increasing'
            temp_high = candle.high
       

        #bos의 기준점 수정정
        if temp_high < candle.high:
            temp_high = candle.high

        if temp_low > candle.low:
            temp_low = candle.low
    

    

def make_entry_point(coin, entry_analysis):
    if entry_analysis['signal']:
        trade_logs = TradeLog.objects.filter(coin=coin)
        win = 0
        lose = 0
        for trade_log in trade_logs:
            if trade_log.profit_loss == 'win':
                win += 1
            elif trade_log.profit_loss == 'lose':
                lose += 1
        if win > lose:
            entry_point= Entry_point(
            coin=coin,
            tag = coin.tag,
            direction = entry_analysis['side'],
            entry_price = entry_analysis['entry'],
            take_profit = entry_analysis['take_profit'],
            stop_loss = entry_analysis['stop_loss']
            )
            return entry_point
        else:
            return None
                


def high_scale_analyze(coin,open_time):

    high_frame_past_prices = Candle_stick.objects.filter(coin=coin).order_by('open_time')
    past_prices = []
    if len( high_frame_past_prices) == 0:
        return 0
    
    for num in range(len( high_frame_past_prices)):

        if high_frame_past_prices[num].open_time <= open_time:

            past_prices.append(high_frame_past_prices[num])

    current_orderblock = orderblock(past_prices[0].high,past_prices[0].low,past_prices[0].high,past_prices[0].low)
    temp_high = 0
    temp_low = 1000000000
    trend = 'increasing' if past_prices[0].close >= past_prices[0].open else 'decreasing'
    #initial_setting----------------------------------------------------------------------------------------------------------



    for i in range(len(past_prices)):

        candle = past_prices[i]
        #상방 bos
        if temp_high < candle.high and trend != 'decreasing':
            
            for j in reversed(range(i)):
                cur_candle = past_prices[j]

                if cur_candle.high == temp_high:
                    if j + 4 <= i: #전 고점 좌표 찾기.
                        demand_high = min(past_prices[j:i], key = lambda x : x.high).high
                        demand_low = min(past_prices[j:i], key = lambda x : x.low).low
                        current_orderblock.demand = { "high": demand_high, "low": demand_low, 'inefficiency' : False, 'unmitigated': True,'open_time':min(past_prices[j:i], key = lambda x : x.low).open_time, 'renewal_time' : candle.open_time}
                        
                        bos = 1

                        for k in range(j,i+1):
                            if k > 0 and len(past_prices)-1 > k:

                                if (past_prices[k+1].low - past_prices[k-1].high)/past_prices[k-1].high > 0.004:
                                    current_orderblock.demand['inefficiency'] = True
                    break
                    
            trend = 'increasing'
        #하방 bos
        
        elif temp_low > candle.low and trend != 'increasing':
 
            for j in reversed(range(i)):

                cur_candle = past_prices[j]

                if cur_candle.low == temp_low :
                    if j + 4 <= i: #전 저점 좌표 찾기.
                        supply_high = max(past_prices[j:i], key = lambda x : x.high).high
                        supply_low = max(past_prices[j:i], key = lambda x : x.low).low
                        current_orderblock.supply = { "high": supply_high, "low": supply_low, 'inefficiency' : False, 'unmitigated': True,'open_time':max(past_prices[j:i], key = lambda x : x.high).open_time, 'renewal_time' : candle.open_time}
                       
                        bos = 1

                        for k in range(j,i+1):
                            if k > 0 and len(past_prices)-1 > k:
                                if (past_prices[k-1].low - past_prices[k+1].high)/past_prices[k+1].high > 0.004:

                                            current_orderblock.supply['inefficiency'] = True
                    break       
                        
                    
                trend = 'decreasing'

        #상방에서 하방 choch
        elif current_orderblock.demand['low'] > candle.close and trend != 'decreasing':

            for j in reversed(range(i)):
                cur_candle = past_prices[j]
              
                if cur_candle.low == current_orderblock.demand['low']: #마지막 bos가 일어난 상방 오더블록 찾기
                    supply_high = max(past_prices[j:i], key = lambda x : x.high).high
                    supply_low = max(past_prices[j:i], key = lambda x : x.low).low
                    current_orderblock.supply = { "high": supply_high, "low": supply_low, 'inefficiency' : False, 'unmitigated': True,'open_time':max(past_prices[j:i], key = lambda x : x.high).open_time, 'renewal_time' : candle.open_time}
                    
                    for k in range(j,i+1):
                        if k > 0 and len(past_prices)-1 > k:
                            if (past_prices[k-1].low - past_prices[k+1].high)/past_prices[k+1].high > 0.004:

                                        current_orderblock.supply['inefficiency'] = True
                    bos = 0
                    break
               
            trend = 'decreasing'
            temp_low = candle.low


        #하방에서 상방 choch
        elif current_orderblock.supply['high'] < candle.close and trend != 'increasing':

            for j in reversed(range(i)):
                cur_candle = past_prices[j]

                if cur_candle.high == current_orderblock.supply['high']:  #마지막 bos가 일어난 히방 오더블록 찾기
                    demand_high = min(past_prices[j:i], key = lambda x : x.high).high
                    demand_low = min(past_prices[j:i], key = lambda x : x.low).low
                    current_orderblock.demand = { "high": demand_high, "low": demand_low, 'inefficiency' : False, 'unmitigated': True,'open_time':min(past_prices[j:i], key = lambda x : x.low).open_time, 'renewal_time' : candle.open_time}
                    
                    for k in range(j,i+1):
                        if k > 0 and len(past_prices)-1 > k:

                            if (past_prices[k+1].low - past_prices[k-1].high)/past_prices[k-1].high > 0.004:
                                current_orderblock.demand['inefficiency'] = True
                    bos = 0
                    break
        
            trend = 'increasing'
            temp_high = candle.high
       

        #bos의 기준점 수정정
        if temp_high < candle.high:
            temp_high = candle.high

        if temp_low > candle.low:
            temp_low = candle.low
    

    return trend, current_orderblock