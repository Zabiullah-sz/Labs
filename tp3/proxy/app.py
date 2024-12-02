from flask import Flask, request, jsonify
import random
import mysql.connector
import logging
import subprocess

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Database configurations
MASTER_DB = {"host": "MANAGER_IP", "user": "root", "password": "password123", "database": "sakila"}
SERVER_DBS = [
    {"host": "MANAGER_IP", "user": "root", "password": "password123", "database": "sakila"},
    {"host": "WORKER1_IP", "user": "root", "password": "password123", "database": "sakila"},
    {"host": "WORKER2_IP", "user": "root", "password": "password123", "database": "sakila"}
]
WORKER_DBS = [
    {"host": "WORKER1_IP", "user": "root", "password": "password123", "database": "sakila"},
    {"host": "WORKER2_IP", "user": "root", "password": "password123", "database": "sakila"}
]

# Get the server with the lowest ping time
def get_fastest_server():
    times = []
    for server_db in SERVER_DBS:
        host = server_db["host"]
        try:
            result = subprocess.run(
                ["ping", "-c", "1", host],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            output = result.stdout
            # Extract time=XX ms from ping output
            time_index = output.find("time=")
            if time_index != -1:
                ping_time = float(output[time_index + 5: output.find(" ms", time_index)])
                times.append((ping_time, server_db))
                logging.info(f"Ping time for {host}: {ping_time} ms")
        except Exception as e:
            logging.error(f"Error pinging {host}: {e}")

    # Sort servers by ping time and return the fastest
    times.sort(key=lambda x: x[0])
    return times[0][1] if times else random.choice(SERVER_DBS)  # Fallback to random if no ping times available

# Execute the query on the specified database
def execute_query(db_config, query):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        logging.info(f"Executing query: {query}")
        cursor.execute(query)

        # Commit changes for non-SELECT queries
        if query.strip().lower().startswith(("insert", "update", "delete")):
            conn.commit()
            result = {"affected_rows": cursor.rowcount}
        else:
            result = cursor.fetchall()

        conn.close()
        logging.info(f"Query executed successfully, result: {result}")
        return result
    except mysql.connector.Error as err:
        logging.error(f"Error: {err}")
        return {"error": str(err)}

@app.route('/query', methods=['POST'])
def route_request():
    data = request.get_json()
    query_type = data.get("type", "read").lower()
    query = data.get("query", "")
    mode = data.get("mode", "random").lower()  # Added mode parameter
    logging.info(f"Received request: type={query_type}, mode={mode}, query={query}")

    if query_type == "write":
        # All write requests go to the master
        result = execute_query(MASTER_DB, query)
    elif query_type == "read":
        if mode == "direct_hit":
            # Direct Hit: All read requests go to the master
            result = execute_query(MASTER_DB, query)
        elif mode == "random":
            # Random mode: Randomly select any server
            server_db = random.choice(WORKER_DBS)
            logging.info(f"Randomly selected server database: {server_db['host']}")
            result = execute_query(server_db, query)
        elif mode == "customized":
            # Customized mode: Choose the fastest server based on ping
            server_db = get_fastest_server()
            logging.info(f"Selected server database based on ping: {server_db['host']}")
            result = execute_query(server_db, query)
        else:
            return jsonify({"error": "Invalid mode"}), 400
    else:
        return jsonify({"error": "Invalid query type"}), 400

    return jsonify({"result": result})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
