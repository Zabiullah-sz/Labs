from flask import Flask, request, jsonify
import random
import mysql.connector
import logging
import subprocess
import time

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

# Benchmark result storage file
BENCHMARK_FILE = "/tmp/benchmark_proxy_result.txt"

# Store benchmark results
benchmark_all_results = {
    "direct_hit": {
        "total_requests": 0,
        "total_read_requests": 0,
        "total_write_requests": 0,
        "total_time": 0,
        "average_time": 0,
    },
    "random": {
        "total_requests": 0,
        "total_read_requests": 0,
        "total_write_requests": 0,
        "total_time": 0,
        "average_time": 0,
    },
    "customized": {
        "total_requests": 0,
        "total_read_requests": 0,
        "total_write_requests": 0,
        "total_time": 0,
        "average_time": 0,
    },
}


def save_benchmark_to_file():
    """
    Save the current benchmarking results for all modes to a file in a formatted way.
    """
    with open(BENCHMARK_FILE, "w") as file:
        file.write("===== Proxy Benchmark Results =====\n\n")
        for mode, data in benchmark_all_results.items():
            file.write(f"--- Mode: {mode.capitalize()} ---\n")
            file.write(f"Total Requests: {data['total_requests']}\n")
            file.write(f"  - Total Read Requests: {data['total_read_requests']}\n")
            file.write(f"  - Total Write Requests: {data['total_write_requests']}\n")
            file.write(f"Total Time Taken: {data['total_time']:.4f} seconds\n")
            file.write(f"Average Time per Request: {data['average_time']:.4f} seconds\n")
            if data['total_write_requests'] > 0:
                avg_write_time = data['total_time'] / data['total_write_requests']
                file.write(f"  - Average Time per Write Request: {avg_write_time:.4f} seconds\n")
            if data['total_read_requests'] > 0:
                avg_read_time = data['total_time'] / data['total_read_requests']
                file.write(f"  - Average Time per Read Request: {avg_read_time:.4f} seconds\n")
            file.write("\n")


def update_benchmark(mode, query_type, cluster_request_time):
    """
    Update the benchmark statistics for a specific mode and query type.

    Parameters:
        mode (str): The mode of operation (e.g., direct_hit, random, customized).
        query_type (str): The type of query (read or write).
        cluster_request_time (float): Time taken for the cluster to respond.
    """
    data = benchmark_all_results[mode]
    data["total_requests"] += 1
    data["total_time"] += cluster_request_time

    # Update specific counters
    if query_type == "read":
        data["total_read_requests"] += 1
    elif query_type == "write":
        data["total_write_requests"] += 1

    # Recalculate average time
    data["average_time"] = data["total_time"] / data["total_requests"]

    # Save the updated benchmark to the file
    save_benchmark_to_file()

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

    server_db = None  # Initialize server database configuration

    if query_type == "write":
        # All write requests go to the master
        server_db = MASTER_DB
    elif query_type == "read":
        if mode == "direct_hit":
            # Direct Hit: All read requests go to the master
            server_db = MASTER_DB
        elif mode == "random":
            # Random mode: Randomly select any server
            server_db = random.choice(WORKER_DBS)
            logging.info(f"Randomly selected server database: {server_db['host']}")
        elif mode == "customized":
            # Customized mode: Choose the fastest server based on ping
            server_db = get_fastest_server()
            logging.info(f"Selected server database based on ping: {server_db['host']}")
        else:
            return jsonify({"error": "Invalid mode"}), 400
    else:
        return jsonify({"error": "Invalid query type"}), 400

    # Benchmark cluster start time (ONLY for the query execution)
    cluster_start_time = time.time()

    # Execute the query on the selected server
    result = execute_query(server_db, query)

    # Benchmark cluster end time
    cluster_end_time = time.time()

    # Calculate the cluster request time
    cluster_request_time = cluster_end_time - cluster_start_time

    # Update benchmarking metrics
    update_benchmark(mode, query_type, cluster_request_time)

    # Log the cluster-specific benchmark result
    logging.info(f"Cluster {server_db['host']} request time: {cluster_request_time:.4f} seconds")
    return jsonify({
        "result": result,
        "cluster_time_taken": f"{cluster_request_time:.4f} seconds"
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
