import requests
import json

login_url = 'http://127.0.0.1:8888/api/auth/login'
payload = {'username': 'admin', 'password': 'Hotspot@123'}
response = requests.post(login_url, json=payload)
token = response.json()['data']['access_token']
headers = {'Authorization': 'Bearer ' + token}

print('=== 测试历史曲线接口 ===')
response = requests.get('http://127.0.0.1:8888/api/trend-chart/history?branch=1&range=1h', headers=headers)
result = response.json()
print('响应结构:')
print(json.dumps(result, indent=2, ensure_ascii=False))

print('\n=== 测试告警历史接口 ===')
response = requests.get('http://127.0.0.1:8888/api/trend-chart/alarm-history?branch=1&range=1h', headers=headers)
result = response.json()
print('响应结构:')
print(json.dumps(result, indent=2, ensure_ascii=False))

print('\n=== 测试阈值接口 ===')
response = requests.get('http://127.0.0.1:8888/api/trend-chart/threshold', headers=headers)
result = response.json()
print('响应结构:')
print(json.dumps(result, indent=2, ensure_ascii=False))