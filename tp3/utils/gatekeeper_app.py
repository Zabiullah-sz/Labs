from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

TRUSTED_HOST_URL = "http://TRUSTED_HOST_IP:5000"

@app.route('/validate', methods=['POST'])
def validate_request():
    data = request.get_json()
    if "query" not in data:
        return jsonify({"error": "Invalid request"}), 400

    response = requests.post(TRUSTED_HOST_URL, json=data)
    return response.json()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
