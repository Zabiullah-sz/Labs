import requests
import time
import os

# Logging to a local text file
log_file = "benchmarks_and_logs/benchmark_logs.txt"

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

    # Track metrics
    total_read_time = 0
    total_write_time = 0

    # Send read requests
    for i in range(num_requests):
        start_read = time.time()
        send_request(i, gatekeeper_url, read_data)
        end_read = time.time()
        total_read_time += end_read - start_read

    # Send write requests
    for i in range(num_requests):
        # Change the write request to insert unique values
        modified_write_data = write_data.copy()
        modified_write_data["query"] = f"INSERT INTO actor (first_name, last_name) VALUES ('BOB', 'CHA{i}');"
        start_write = time.time()
        send_request(i + num_requests, gatekeeper_url, modified_write_data)
        end_write = time.time()
        total_write_time += end_write - start_write

    end_time = time.time()
    total_time = end_time - start_time

    avg_read_time = total_read_time / num_requests
    avg_write_time = total_write_time / num_requests

    # Log results
    log_to_file(f"\nResults for mode '{mode}':")
    log_to_file(f"Total time taken: {total_time:.2f} seconds")
    log_to_file(f"Average time per read: {avg_read_time:.4f} seconds")
    log_to_file(f"Average time per write: {avg_write_time:.4f} seconds")
    log_to_file(f"Average time per request: {total_time / (2 * num_requests):.4f} seconds")

    print(f"\nResults for mode '{mode}':")
    print(f"Total time taken: {total_time:.2f} seconds")
    print(f"Average time per read: {avg_read_time:.4f} seconds")
    print(f"Average time per write: {avg_write_time:.4f} seconds")
    print(f"Average time per request: {total_time / (2 * num_requests):.4f} seconds")

# Main benchmark function
def run_benchmark(gatekeeper_url):
    # Ensure the directory exists
    # Clear the log file
    open(log_file, "w").close()

    # Define common request data
    read_data = {"type": "read", "query": "SELECT * FROM actor WHERE first_name = 'BOB' LIMIT 3;", "mode": ""}
    write_data = {"type": "write", "query": "INSERT INTO actor (first_name, last_name) VALUES ('BOB', 'CHA');", "mode": ""}

    # Run benchmarks for each mode
    for mode in ["direct_hit", "random", "customized"]:
        read_data["mode"] = mode
        write_data["mode"] = mode
        benchmark_gatekeeper(gatekeeper_url + "/validate", 5, read_data, write_data, mode)

    # Summarize results
    print("\nBenchmarking completed. Results logged in 'benchmarks_and_logs/benchmark_logs.txt'.")