import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'hotspot_api.settings'
import django
django.setup()
from django.urls import get_resolver, resolve

r = get_resolver()
print("All URL patterns:")
for pattern in r.url_patterns:
    print(f"  {pattern.pattern}")

print("\nResolve /api/history/alarm/:")
match = resolve('/api/history/alarm/')
print(f"  func: {match.func.__name__}, name: {match.url_name}")
print(f"  kwargs: {match.kwargs}")
