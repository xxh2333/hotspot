import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'hotspot_api.settings'
import django
django.setup()

from django.urls import resolve, Resolver404, get_resolver

url = '/api/history/alarm/'
try:
    match = resolve(url)
    print(f'OK: {url} -> {match.func.__name__} ({match.url_name})')
    print(f'  kwargs: {match.kwargs}')
except Exception as e:
    print(f'ERROR: {e}')

url2 = '/api/history/temperature/'
try:
    match = resolve(url2)
    print(f'OK: {url2} -> {match.func.__name__} ({match.url_name})')
except Exception as e:
    print(f'ERROR: {e}')

url3 = '/api/history/temperature/summary/'
try:
    match = resolve(url3)
    print(f'OK: {url3} -> {match.func.__name__} ({match.url_name})')
except Exception as e:
    print(f'ERROR: {e}')
