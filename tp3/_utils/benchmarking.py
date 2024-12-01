import aiohttp
import asyncio
import time

def get_public_ip(ec2, instance_id):
    response = ec2.describe_instances(InstanceIds=[instance_id])
    public_ip = response['Reservations'][0]['Instances'][0].get('PublicIpAddress')
    
    if public_ip:
        return public_ip
    else:
        raise ValueError(f"No public IP address found for instance {instance_id}")

# Function to send requests to a specific endpoint
async def call_endpoint_http(session, request_num, url):
    headers = {'content-type': 'application/json'}
    try:
        async with session.get(url, headers=headers) as response:
            status_code = response.status
            response_json = await response.json()
            print(f"Request {request_num}: Status Code: {status_code}")
            print(f"Response Json {response_json}")
            return status_code, response_json
    except Exception as e:
        print(f"Request {request_num}: Failed - {str(e)}")
        return None, str(e)

# Function to benchmark the cluster
async def benchmark_cluster(cluster_url, num_requests=1000):
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = [call_endpoint_http(session, i, cluster_url) for i in range(num_requests)]
        await asyncio.gather(*tasks)
    
    end_time = time.time()
    total_time = end_time - start_time
    print(f"\nTotal time taken: {total_time:.2f} seconds")
    print(f"Average time per request: {total_time / num_requests:.4f} seconds")

# Main benchmark function
async def run_benchmark(lb_public_ip):
    cluster1_url = f"http://{lb_public_ip}:80/cluster1"
    cluster2_url = f"http://{lb_public_ip}:80/cluster2"
    
    print("\nBenchmarking Cluster 1")
    await benchmark_cluster(cluster1_url)
    
    print("\nBenchmarking Cluster 2")
    await benchmark_cluster(cluster2_url)