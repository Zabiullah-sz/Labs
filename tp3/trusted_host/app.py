from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

PROXY_URL = "http://PROXY_IP:5000"

@app.route('/', methods=['POST'])
def forward_request():
    data = request.get_json()
    response = requests.post(PROXY_URL + "/query", json=data)
    return response.json()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
