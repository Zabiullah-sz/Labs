import requests
import time

# Logging to a local text file
log_file = "benchmark_logs.txt"

# Function to write logs to a file
def log_to_file(message):
    with open(log_file, "a") as file:
        file.write(message + "\n")

# Function to send requests to a specific endpoint
def send_request(request_num, url, json_data):
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, json=json_data)
        status_code = response.status_code
        response_json = response.json()
        
        log_to_file(f"Request {request_num}: Status Code: {status_code}")
        log_to_file(f"Response: {response_json}")
        
        return status_code, response_json
    except Exception as e:
        error_message = f"Request {request_num}: Failed - {str(e)}"
        log_to_file(error_message)
        return None, str(e)

# Function to benchmark the Gatekeeper
def benchmark_gatekeeper(gatekeeper_url, num_requests, read_data, write_data, mode):
    log_to_file(f"\nBenchmarking '{mode}' mode...")
    print(f"\nBenchmarking '{mode}' mode...")

    start_time = time.time()

    # Send read requests
    for i in range(num_requests):
        send_request(i, gatekeeper_url, read_data)

    # Send write requests
    for i in range(num_requests):
        # Change the write request to insert unique values
        modified_write_data = write_data.copy()
        modified_write_data["query"] = f"INSERT INTO actor (first_name, last_name) VALUES ('John', 'Doe{i}');"
        send_request(i + num_requests, gatekeeper_url, modified_write_data)

    end_time = time.time()
    total_time = end_time - start_time

    log_to_file(f"\nTotal time taken for {mode}: {total_time:.2f} seconds")
    log_to_file(f"Average time per request: {total_time / (2 * num_requests):.4f} seconds")
    print(f"\nTotal time taken for {mode}: {total_time:.2f} seconds")
    print(f"Average time per request: {total_time / (2 * num_requests):.4f} seconds")

# Main benchmark function
def run_benchmark(gatekeeper_url):
    # Clear the log file
    open(log_file, "w").close()

    # Define common request data
    read_data = {"type": "read", "query": "SELECT * FROM actor;", "mode": ""}
    write_data = {"type": "write", "query": "INSERT INTO actor (first_name, last_name) VALUES ('John', 'Doe');", "mode": ""}

    # Run benchmarks for each mode
    for mode in ["direct_hit", "random", "customized"]:
        read_data["mode"] = mode
        write_data["mode"] = mode
        benchmark_gatekeeper(gatekeeper_url + "/validate", 10, read_data, write_data, mode)
