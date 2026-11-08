"""Custom OpenWeatherMap MCP server (stdio), exposing current + short-range forecast."""
import os
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('Travel Weather MCP')
BASE = 'https://api.openweathermap.org/data/2.5'


def fetch_weather(endpoint: str, city: str) -> dict:
    api_key = os.getenv('OPENWEATHER_API_KEY', '')
    if not api_key:
        return {'error': 'OPENWEATHER_API_KEY not configured'}
    if not city.strip():
        return {'error': 'City is required'}
    try:
        response = requests.get(f'{BASE}/{endpoint}', params={
            'q': city, 'appid': api_key, 'units': 'metric',
        }, timeout=12)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        return {'error': f'Weather provider failure: {exc}'}


@mcp.tool()
def get_current_weather(city: str) -> dict:
    """Get present-day weather, NOT travel-date weather for distant future trips."""
    data = fetch_weather('weather', city)
    if 'error' in data:
        return data
    return {'city': data.get('name', city), 'temperature_c': data['main']['temp'],
            'humidity': data['main']['humidity'], 'condition': data['weather'][0]['description'],
            'observed_unix': data.get('dt'), 'scope': 'current conditions only'}


@mcp.tool()
def get_forecast(city: str) -> dict:
    """Get next up to five 3-hour entries, NOT a 5-day or 7-day forecast."""
    data = fetch_weather('forecast', city)
    if 'error' in data:
        return data
    return {'city': data.get('city', {}).get('name', city),
            'entries': [{'time_utc': row['dt_txt'], 'temperature_c': row['main']['temp'],
                         'condition': row['weather'][0]['description']}
                        for row in data.get('list', [])[:5]],
            'scope': 'five 3-hour entries (~15 hours), not a whole trip forecast'}


if __name__ == '__main__':
    mcp.run()
