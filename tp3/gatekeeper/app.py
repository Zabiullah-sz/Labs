from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

TRUSTED_HOST_URL = "http://TRUSTED_HOST_IP:5000"

VALID_TYPES = {"read", "write"}
VALID_MODES = {"random", "direct_hit", "customized"}

@app.route('/validate', methods=['POST'])
def validate_request():
    data = request.get_json()
    query = data.get("query")
    req_type = data.get("type")
    mode = data.get("mode")

    if not query or not isinstance(query, str):
        return jsonify({"error": "Invalid request: 'query' must be a non-empty string"}), 400

    if req_type not in VALID_TYPES:
        return jsonify({"error": f"Invalid request: 'type' must be one of {VALID_TYPES}"}), 400
    
    if mode not in VALID_MODES:
        return jsonify({"error": f"Invalid request: 'type' must be one of {VALID_TYPES}"}), 400

    if set(data.keys()) != {"type", "mode", "query",}:
        return jsonify({"error": "Invalid request: request must contain exactly 'type', 'mode', and 'query' fields"}), 400

    response = requests.post(TRUSTED_HOST_URL, json=data)
    return response.json()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
