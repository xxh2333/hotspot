import requests

login_url = 'http://127.0.0.1:8888/api/auth/login'
payload = {'username': 'admin', 'password': 'Hotspot@123'}
response = requests.post(login_url, json=payload)
token = response.json()['data']['access_token']
print('获取token成功')

alarm_url = 'http://127.0.0.1:8888/api/trend-chart/alarm-history?branch=1&range=24h'
headers = {'Authorization': 'Bearer ' + token}
response = requests.get(alarm_url, headers=headers)
result = response.json()
print('接口响应: code=%s, msg=%s' % (result['code'], result['msg']))
if result.get('data'):
    data = result['data']
    print('告警条数: %d' % len(data.get('data', [])))
    if data.get('data'):
        print('第一条告警: %s' % data['data'][0])
