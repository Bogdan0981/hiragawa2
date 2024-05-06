import streamlit as st
import psycopg2
import requests
from datetime import datetime, timedelta
import json
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objs as go
from scipy.interpolate import make_interp_spline
import numpy as np



# проверка подключения к инету
def check_connection():
    try:
        requests.get('http://www.google.com', timeout=5)
        return True
    except requests.ConnectionError:
        return False
    

# подключение к бд
def connect_db():
    return psycopg2.connect (
        dbname = 'postgres',
        user = 'postgres',
        password = 'kb0904',
        host = 'localhost',
        port = '5433'
    )
# функция connect_db возвращает обьект, котороый находиться в бд, то есть у нас есть все таблицы из бд

def get_hourly_forecast(hourly_forecast):
    forecast_intervals = hourly_forecast[:8]
    return forecast_intervals

def get_weather_data_from_api(city):
    api_key = "2624fd25b511ea7d85afbcb3f9439698"
    weather_url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric"
    
    current_weather = requests.get(weather_url).json()
    forecast = requests.get(forecast_url).json()

    forecast_24 = get_hourly_forecast(forecast['list'])

    return current_weather, forecast, forecast_24


# получение данных из бд
def get_current_weather_from_db(city):
    with connect_db() as con:
        with con.cursor() as cur:
            cur.execute('SELECT record_time, temperature, humidity, cloudiness, wind_speed, city_name FROM current_weather WHERE city_name = %s ORDER BY record_time DESC LIMIT 1', (city,))
            data = cur.fetchone()
            if data:
                return{
                    'name': city,
                    'main': {
                        'temp': data[1],
                        'humidity': data[2]
                    },
                    'clouds': {
                        'all': data[3],
                    },
                    'wind': {
                        'speed': data[4],
                    }
                }
            else:
                return None
            
# получение прогноза погоды из бд
def get_forecast_from_db(city):
    with connect_db() as con:
        with con.cursor() as cur:
            # Здесь меняем DESC на ASC, чтобы сортировать данные по возрастанию
            cur.execute('SELECT date_time, temp_min, temp_max, humidity, cloudiness, wind_speed FROM forecast WHERE city_name = %s ORDER BY date_time ASC', (city,))
            rows = cur.fetchall()
            if rows:
                forecast_list = []
                for row in rows:
                    forecast_entry = {
                        'dt': int(datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").timestamp()),  # Преобразуем date_time в timestamp
                        'main': {
                            'temp_min': row[1],
                            'temp_max': row[2],
                            'humidity': row[3]
                        },
                        'clouds': {
                            'all': row[4]
                        },
                        'wind': {
                            'speed': row[5]
                        }
                    }
                    forecast_list.append(forecast_entry)
                return {'list': forecast_list}  # Возвращаем словарь, имитирующий структуру API
            else:
                print(f'No forecast data found for city: {city}')
    return None

# функция отображения главной страницы
def main_page():
    st.title('Application to see current weather and forecast for 5 days')
    st.write("This application which was created by Bohdan Kalgan and Oleksandr Sytnyk is used to see current weeather in your city and forecast in 5 days")
    st.sidebar.title("Please write your city here to see weather")
    st.sidebar.write('Please write your city and press "Enter" or press the buttont tio see the weather')
    st.sidebar.text_input('City name:', key='city', on_change=load_weater)

    if st.sidebar.button('Show weather'):
        load_weater()

# функция заргрузки погоды, она чекает есть инет или нету и в зависимисти от инета выбирает спопоб выписывания погоды
def load_weater():
    city_input = st.session_state.city
    if city_input:
        if check_connection():
            current_weather, forecast, forecast_24 = get_weather_data_from_api(city_input)
        else:
            st.warning('No internet connection. Data was taken from databsse')
            current_weather = get_current_weather_from_db(city_input)
            forecast = get_forecast_from_db(city_input)
        
        if current_weather and forecast:
            st.session_state.current_weather = current_weather
            st.session_state.forecast = forecast
            st.session_state.forecast_24 = forecast_24
            st.rerun()
        else:
            st.error('There is not weather data. Please, try again')

# функция для отображения страницы погоды
def weather_page():
    st.title('Weather page for show current weather and forecast')
    if st.button('Return to main page'):
        if "current_weather" in st.session_state:
            del st.session_state['current_weather']
        if "forecast" in st.session_state:
            del st.session_state['forecast']
        st.rerun()
    current_weather = st.session_state.get('current_weather')
    forecast = st.session_state.get('forecast')
    forecast_24 = st.session_state.get('forecast_24')
    if current_weather:
        display_weather(current_weather, forecast, forecast_24)
    else:
        st.error('There is not weather data. Please, try again')

def display_forecast_graph(forecast_24):
    times = []
    temperatures = []
    wind_speeds = []
    
    for forecast in forecast_24:
        forecast_time = datetime.fromtimestamp(forecast['dt']).strftime('%H:%M')
        times.append(forecast_time)
        
        temperature = forecast['main']['temp']
        temperatures.append(temperature)
        
        wind_speed = forecast['wind']['speed']
        wind_speeds.append(wind_speed)

    trace_temp = go.Scatter(
        x=times, 
        y=temperatures, 
        mode='lines+text',
        text=[f"{t}°C" for t in temperatures],
        textposition="top center",
        line=dict(width=3, shape='spline', smoothing=1, color='#90a955'),
        textfont=dict(size=16)
    )
    

    annotations = [
        dict(
            x=times[i], 
            y=min(temperatures) - 1,
            text=f"{ws} м/с", 
            showarrow=False,
            xanchor='center',
            yanchor='top',
            font=dict(color='blue', size=16)
        ) for i, ws in enumerate(wind_speeds)
    ]
    
    layout = go.Layout(
        title='Изменение температуры по времени',
        xaxis=dict(
            tickfont=dict(size=15)
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False
        ),
        margin=dict(l=40, r=40, t=40, b=40),
        showlegend=False,
        annotations=annotations
    )
    
    fig = go.Figure(data=[trace_temp], layout=layout)
    st.plotly_chart(fig, use_container_width=True)



# функция для отображения текущей погоды
def display_weather(current_weather, forecast, forecast_24):
    city_name = current_weather.get('name')
    st.subheader(f'Weather in {city_name}:', datetime.now().strftime("%H:%M:%S"))
    cur_weather = current_weather.get('main')
    cloudiness = current_weather.get('clouds')
    wind = current_weather.get('wind')
    st.write('Current weather: ')
    st.write(f'Temperaturte: {cur_weather.get("temp")}°C')
    st.write(f'Humdity: {cur_weather.get("shumudity")}')
    st.write(f'Cloudiness: {cloudiness.get("all")}')
    st.write(f'Wind speed: {wind.get("speed")}')


    st.subheader('Forecast for 5 days')
    if forecast:
        display_forecast(forecast)
        display_forecast_graph(forecast_24)
    else:
        st.error('There is not data about current weather. Please, try again')


# фукуция отображение прогноза погоды
def display_forecast(forecast):
    today = datetime.now().date()
    forecast_list = forecast.get('list')
    date_set = set()
    for forecast in forecast_list:
        forecast_date = datetime.fromtimestamp(forecast.get('dt')).date()
        if forecast_date > today and forecast_date not in date_set and len(date_set) < 5:
            date_set.add(forecast_date)
            temp_max = forecast.get('main', {}).get('temp_max')
            temp_min = forecast.get('main', {}).get('temp_min')
            humidity = forecast.get('main', {}).get('humidity')
            cloudiness = forecast.get('clouds', {}).get('all')
            wind_speed = forecast.get('wind', {}).get('speed')
            st.write(f'Date: {forecast_date.strftime("%d %B %Y")}')
            st.write(f'Maxmimum temperature: {temp_max}°C')
            st.write(f'Minimum temperature: {temp_min}°C')
            st.write(f'Humidity: {humidity}')
            st.write(f'Cloudiness: {cloudiness}')
            st.write(f'Wind speed: {wind_speed}')
            st.write('----')


        
if 'current_weather' not in st.session_state:
    main_page()
else:
    weather_page()