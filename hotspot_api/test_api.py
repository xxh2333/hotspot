import requests
import json

# 登录获取token
login_url = 'http://127.0.0.1:8888/api/auth/login'
payload = {'username': 'admin', 'password': 'Hotspot@123'}
response = requests.post(login_url, json=payload)
token = response.json()['data']['access_token']
print('获取token成功')

# 测试历史曲线接口
history_url = 'http://127.0.0.1:8888/api/trend-chart/history?branch=1&range=1h'
headers = {'Authorization': 'Bearer ' + token}
response = requests.get(history_url, headers=headers)
result = response.json()
print('接口响应: code=%s, msg=%s' % (result['code'], result['msg']))
if result.get('data'):
    data = result['data']
    print('数据条数: %d' % len(data.get('data', [])))
    if data.get('data'):
        print('第一条数据: %s' % data['data'][0])
