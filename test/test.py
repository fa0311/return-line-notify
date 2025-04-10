import requests

API_URI = "http://127.0.0.1:3333/api/notify"

headers = {"Authorization": "Bearer 335874895"}


data = {"message": "test"}

requests.post(API_URI, headers=headers, data=data)
