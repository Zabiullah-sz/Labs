# proxy_app.py
from flask import Flask, request, jsonify
import random
import mysql.connector
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

MANAGER_DB = {"host": "MANAGER_IP", "user": "root", "password": "password123", "database": "sakila"}
WORKER_DBS = [
    {"host": "WORKER1_IP", "user": "root", "password": "password123", "database": "sakila"},
    {"host": "WORKER2_IP", "user": "root", "password": "password123", "database": "sakila"}
]

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
    logging.info(f"Received request: type={query_type}, query={query}")

    if query_type == "write":
        result = execute_query(MANAGER_DB, query)
    elif query_type == "read":
        worker_db = random.choice(WORKER_DBS)
        logging.info(f"Selected worker database: {worker_db['host']}")
        result = execute_query(worker_db, query)
    else:
        logging.warning("Invalid query type received")
        return jsonify({"error": "Invalid query type"}), 400

    return jsonify({"result": result})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
