import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import pandas as pd
from trade.models import Coin, TradeLog, Candle_stick,Order_block, Entry_point
from django_plotly_dash import DjangoDash
import datetime

app = DjangoDash('watch_list')


candle_sizes = ['5m', '15m']
log_types = ['back_testing','real_trading']
total_win = len(TradeLog.objects.filter(profit_loss = 'win'))
total_lose = len(TradeLog.objects.filter(profit_loss = 'lose'))

def load_layout():
    tags = Entry_point.objects.values_list('tag', flat=True).distinct()
    layout = html.Div([
    html.H1(f"현재 진입 조건을 만족한 코인", style={"textAlign": "center"}),

    html.Div([
        html.Label("코인 선택"),
        dcc.Dropdown(
            id='coin-selector',
            options=[{'label': tag, 'value': tag} for tag in tags],
            value='LTC',
            clearable=False
        ),
    ], style={'width': '30%', 'display': 'inline-block'}),

    html.Div([
        html.Label("캔들 사이즈 선택"),
        dcc.Dropdown(
            id='candle-size-selector',
            options=[{'label': size, 'value': size} for size in candle_sizes],
            value='15m',
            clearable=False
        ),
    ], style={'width': '30%', 'display': 'inline-block', 'marginLeft': '20px'}),

    html.Div([
        html.Label("로그 타입 선택"),
        dcc.Dropdown(
            id='log-type-selector',
            options=[{'label': log_type, 'value': log_type} for log_type in log_types],
            value='back_testing',
            clearable=False
        ),
    ], style={'width': '30%', 'display': 'inline-block', 'marginLeft': '20px'}),

    dcc.Graph(id='candle-chart')
])
    return layout

app.layout = load_layout

@app.callback(
    Output('candle-chart', 'figure'),
    Input('coin-selector', 'value'),
    Input('candle-size-selector', 'value'),
    Input('log-type-selector', 'value'),
)
def update_chart(selected_tag, candle_size, log_type):

    coin = Coin.objects.filter(tag=selected_tag, candle_size=candle_size).first()
    if not coin:
        return go.Figure()

    candles = Candle_stick.objects.filter(coin=coin).order_by('open_time')
    trades = TradeLog.objects.filter(coin=coin).order_by('opened_at')

    df = pd.DataFrame([{
        'open_time': c.open_time,
        'open': c.open,
        'high': c.high,
        'low': c.low,
        'close': c.close
    } for c in candles])
    
    df['formatted_time'] = df['open_time'].copy().apply(
    lambda x: datetime.datetime.utcfromtimestamp(float(x) / 1000).strftime('%Y-%m-%d %H:%M:%S')
    )
    orderblocks = Order_block.objects.filter(coin=coin).values_list('open_time', flat=True)
    long_entry = trades.filter(direction='BUY').values_list('opened_at', flat=True)
    short_entry = trades.filter(direction='SELL').values_list('opened_at', flat=True)
    long_exit = trades.filter(direction='BUY').exclude(closed_at=None).values_list('closed_at', flat=True)
    short_exit = trades.filter(direction='SELL').exclude(closed_at=None).values_list('closed_at', flat=True)
    win = trades.filter(profit_loss = 'win')
    lose = trades.filter(profit_loss = 'lose')
    entry_price = Entry_point.objects.get(coin=coin).entry_price
    stop_loss = Entry_point.objects.get(coin=coin).stop_loss
    take_profit = Entry_point.objects.get(coin=coin).take_profit


    def time_to_idx(series):
        return df.index[df['open_time'].isin(series)].tolist()

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df['formatted_time'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
                increasing_line_color='black', decreasing_line_color='black', name="전체 캔들"
            ),
            go.Candlestick(
                x=df['formatted_time'].iloc[time_to_idx(orderblocks)],
                open=df['open'].iloc[time_to_idx(orderblocks)],
                high=df['high'].iloc[time_to_idx(orderblocks)],
                low=df['low'].iloc[time_to_idx(orderblocks)],
                close=df['close'].iloc[time_to_idx(orderblocks)],
                increasing_line_color='purple', decreasing_line_color='purple', name="오더블록"
            ),
            go.Candlestick(
                x=df['formatted_time'].iloc[time_to_idx(long_entry)],
                open=df['open'].iloc[time_to_idx(long_entry)],
                high=df['high'].iloc[time_to_idx(long_entry)],
                low=df['low'].iloc[time_to_idx(long_entry)],
                close=df['close'].iloc[time_to_idx(long_entry)],
                increasing_line_color='limegreen', decreasing_line_color='limegreen', name="롱 진입"
            ),
            go.Candlestick(
                x=df['formatted_time'].iloc[time_to_idx(long_exit)],
                open=df['open'].iloc[time_to_idx(long_exit)],
                high=df['high'].iloc[time_to_idx(long_exit)],
                low=df['low'].iloc[time_to_idx(long_exit)],
                close=df['close'].iloc[time_to_idx(long_exit)],
                increasing_line_color='skyblue', decreasing_line_color='skyblue', name="롱 청산"
            ),
            go.Candlestick(
                x=df['formatted_time'].iloc[time_to_idx(short_entry)],
                open=df['open'].iloc[time_to_idx(short_entry)],
                high=df['high'].iloc[time_to_idx(short_entry)],
                low=df['low'].iloc[time_to_idx(short_entry)],
                close=df['close'].iloc[time_to_idx(short_entry)],
                increasing_line_color='red', decreasing_line_color='red', name="숏 진입"
            ),
            go.Candlestick(
                x=df['formatted_time'].iloc[time_to_idx(short_exit)],
                open=df['open'].iloc[time_to_idx(short_exit)],
                high=df['high'].iloc[time_to_idx(short_exit)],
                low=df['low'].iloc[time_to_idx(short_exit)],
                close=df['close'].iloc[time_to_idx(short_exit)],
                increasing_line_color='yellow', decreasing_line_color='yellow', name="숏 청산"
            )
        ],
        layout=go.Layout(
            title=f"{selected_tag} {candle_size} 트레이딩 내역 win_rate : {len(win)} loss_rate : {len(lose)}",
            xaxis_rangeslider_visible=False,
            template="plotly_white",
            shapes=[
            dict(
                type='line',
                xref='paper',  
                x0=0,
                x1=1,
                yref='y',
                y0=entry_price,
                y1=entry_price,
                line=dict(
                    color='purple',
                    width=2,
                    dash='dash'  
                )
            ),
            dict(
                type='line',
                xref='paper',  
                x0=0,
                x1=1,
                yref='y',
                y0=stop_loss,
                y1=stop_loss,
                line=dict(
                    color='red',
                    width=2,
                    dash='dash' 
                )
            ),
            dict(
                type='line',
                xref='paper',  
                x0=0,
                x1=1,
                yref='y',
                y0=take_profit,
                y1=take_profit,
                line=dict(
                    color='green',
                    width=2,
                    dash='dash' 
                )
            ),
            
        ]
        )
    )

    return fig