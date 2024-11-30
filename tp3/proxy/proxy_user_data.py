def get_user_data(manager_ip, worker1_ip, worker2_ip):
    return f"""#!/bin/bash
exec > /var/log/proxy_setup.log 2>&1

# Update and install necessary packages
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3-pip

# Install Flask and other dependencies
sudo pip3 install flask mysql-connector-python requests

# Create proxy application script
cat <<EOF > /home/ubuntu/proxy_app.py
from flask import Flask, request, jsonify
import random
import mysql.connector

app = Flask(__name__)

# Database configurations
MANAGER_DB = {{"host": "{manager_ip}", "user": "root", "password": "password123", "database": "sakila"}}
WORKER_DBS = [
    {{"host": "{worker1_ip}", "user": "root", "password": "password123", "database": "sakila"}},
    {{"host": "{worker2_ip}", "user": "root", "password": "password123", "database": "sakila"}}
]

def execute_query(db_config, query):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    return result

@app.route('/query', methods=['POST'])
def route_request():
    data = request.get_json()
    query_type = data.get("type", "read").lower()
    query = data.get("query", "")

    if query_type == "write":
        # All writes go to the manager
        result = execute_query(MANAGER_DB, query)
    elif query_type == "read":
        # Randomly select a worker for read operations
        worker_db = random.choice(WORKER_DBS)
        result = execute_query(worker_db, query)
    else:
        return jsonify({{"error": "Invalid query type"}}), 400

    return jsonify({{"result": result}})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF

# Run proxy application
nohup python3 /home/ubuntu/proxy_app.py &
"""
