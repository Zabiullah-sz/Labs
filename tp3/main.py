import boto3
import time
from _utils.create_security_group import create_security_group, ensure_security_group_rules
from _utils.ec2_instances_launcher import launch_ec2_instance
from _utils.create_key_pair import generate_key_pair
from dotenv import load_dotenv
from gatekeeper.user_data import get_gatekeeper_user_data
from _utils.benchmarking import run_benchmark
from _utils.run_command_instance import establish_ssh_via_bastion, generate_iptables_command, run_command, retrieve_remote_files
from trusted_host.user_data import get_trusted_host_user_data
from manager.user_data import get_manager_user_data
from workers.user_data import get_worker_user_data
from proxy.user_data import get_proxy_user_data
from _utils.setup_nat_gateway import setup_nat_gateway
import os

# Constants
AWS_REGION = "us-east-1"
KEY_PAIR_NAME = "tp3-key-pair"

# Step 1: Load AWS credentials
os.environ.pop("aws_access_key_id", None)
os.environ.pop("aws_secret_access_key", None)
os.environ.pop("aws_session_token", None)
load_dotenv()

aws_access_key_id = os.getenv("aws_access_key_id")
aws_secret_access_key = os.getenv("aws_secret_access_key")
aws_session_token = os.getenv("aws_session_token")

# Step 2: Initialize EC2 client
ec2 = boto3.client(
    "ec2",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    aws_session_token=aws_session_token,
    region_name=AWS_REGION,
)

# Step 3: Generate Key Pair
key_pair_path = generate_key_pair(ec2, KEY_PAIR_NAME)

# Step 4: Create Security Groups
print("\n\nCreating security groups...")
public_sg_id = create_security_group(
    ec2_client=ec2,
    group_name="public-sg",
    group_description="Public Security Group",
    rules=[
        {
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,           # Allow SSH
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        },
        {
            'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        },
        {
            'IpProtocol': 'tcp',
            'FromPort': 5000,
            'ToPort': 5000,     # Allow Flask
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        },
        {
            'IpProtocol': 'tcp',
            'FromPort': 443,
            'ToPort': 443,      # Allow HTTPS
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        },
        {
            'IpProtocol': 'icmp',
            'FromPort': -1,
            'ToPort': -1,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]   # Allow ICMP
        },
    ],
)

private_sg_id = create_security_group(
    ec2_client=ec2,
    group_name="private-sg",
    group_description="Private Security Group",
    rules=[
        {
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'UserIdGroupPairs': [{'GroupId': public_sg_id}]
        }
    ],
)

print("Modifying security group rules...")

# Add communication rules
proxy_to_cluster_rules = [
    {
        'IpProtocol': 'tcp',
        'FromPort': 3306,
        'ToPort': 3306,
        'UserIdGroupPairs': [{'GroupId': private_sg_id}]
    }
]
ensure_security_group_rules(ec2, private_sg_id, proxy_to_cluster_rules)

trusted_host_rules = [
    {
        'IpProtocol': 'tcp',
        'FromPort': 5000,
        'ToPort': 5000,
        'IpRanges': [{'CidrIp': '172.31.0.0/16'}]
    }
]
ensure_security_group_rules(ec2, private_sg_id, trusted_host_rules)

# Step 4: Setup NAT Gateway
print("\n\nSetting up NAT Gateway...")
public_subnet, private_subnet = setup_nat_gateway(ec2)

# Step 5: Launch Instances
print("\n\nLaunching instances...")

# Bastion Host
bastion_instance = launch_ec2_instance(
    ec2,
    key_pair_name=KEY_PAIR_NAME,
    security_group_id=public_sg_id,
    public_ip=True,
    tag=("Name", "BastionHost"),
)

# Manager Instance
manager_instance = launch_ec2_instance(
    ec2,
    key_pair_name=KEY_PAIR_NAME,
    security_group_id=private_sg_id,
    public_ip=False,
    subnet_id=private_subnet,
    user_data=get_manager_user_data(),
    tag=("Name", "Manager"),
)

manager_ip = manager_instance[0]["PrivateIpAddress"]

# Worker Instances
worker_instances = []
for i in range(2):
    worker = launch_ec2_instance(
        ec2,
        key_pair_name=KEY_PAIR_NAME,
        security_group_id=private_sg_id,
        public_ip=False,
        subnet_id=private_subnet,
        user_data=get_worker_user_data(manager_ip, i + 2),
        tag=("Name", f"Worker-{i + 2}"),
    )
    worker_instances.append(worker)
worker1_ip = worker_instances[0][0]["PrivateIpAddress"]
worker2_ip = worker_instances[1][0]["PrivateIpAddress"]


# Proxy Instance
proxy_instance = launch_ec2_instance(
    ec2,
    key_pair_name=KEY_PAIR_NAME,
    security_group_id=private_sg_id,
    public_ip=False,
    subnet_id=private_subnet,
    user_data=get_proxy_user_data(manager_ip, worker1_ip, worker2_ip),
    tag=("Name", "Proxy"),
)

proxy_ip = proxy_instance[0]["PrivateIpAddress"]

# Trusted Host
trusted_host_instance = launch_ec2_instance(
    ec2,
    key_pair_name=KEY_PAIR_NAME,
    security_group_id=private_sg_id,
    public_ip=False,
    subnet_id=private_subnet,
    user_data=get_trusted_host_user_data(proxy_ip),
    tag=("Name", "TrustedHost"),
)

trusted_host_ip = trusted_host_instance[0]["PrivateIpAddress"]

# Gatekeeper
gatekeeper_instance = launch_ec2_instance(
    ec2,
    key_pair_name=KEY_PAIR_NAME,
    security_group_id=public_sg_id,
    public_ip=True,
    subnet_id=public_subnet,
    user_data=get_gatekeeper_user_data(trusted_host_ip),
    tag=("Name", "Gatekeeper"),
)

gatekeeper_ip = gatekeeper_instance[0]["PrivateIpAddress"]



print("All instances launched.")


# sleep for 4 minutes to allow instances to be ready, make it with a loop so we know the progress after every minute
for i in range(4):
    print(f"Waiting for instances to be ready... {i+1}/4")
    time.sleep(60)

# Send iptables commands to each private instance
instances_and_preceding_ips = [
    (trusted_host_ip, gatekeeper_ip),  # Trusted Host
    (proxy_ip, trusted_host_ip),      # Proxy
    (manager_ip, proxy_ip),
    (worker1_ip, proxy_ip),
    (worker2_ip, proxy_ip)
]

verification_command = "sudo iptables -L -v -n"
bastion_ip = bastion_instance[0]["PublicDnsName"]

print("\n\nConfiguring iptables for private instances...")
for instance_ip, preceding_ip in instances_and_preceding_ips:
    # Determine the role of the instance and set appropriate port
    if instance_ip == manager_ip:
        instance_role = "manager"
        port = 3306  # MySQL port for manager
    elif instance_ip in [worker1_ip, worker2_ip]:
        instance_role = "worker"
        port = 3306  # MySQL port for workers
    else:
        instance_role = "other"
        port = 5000  # Default to port 5000 for other instances

    # Generate iptables command based on the instance role and port
    iptables_command = generate_iptables_command(preceding_ip, port)
    ssh = establish_ssh_via_bastion(bastion_ip, instance_ip, "temp/tp3-key-pair.pem")
    if ssh:
        print(f"Configuring iptables for {instance_role} instance ({instance_ip}) to accept traffic only from {preceding_ip} on port {port}...")
        output, error = run_command(ssh, iptables_command)
        print(f"Verifying iptables rules on {instance_ip}...")
        output2, error = run_command(ssh, verification_command)
        if error:
            print(f"Error configuring iptables on {instance_ip}: {error}")
        else:
            print(f"Successfully configured iptables on {instance_ip}")
            print(f"iptables rules on {instance_ip}:\n{output2}")
        ssh.close()
    else:
        print(f"Failed to connect to instance {instance_ip} via Bastion Host.")

print("\n\nBenchmarking...")
gatekeeper_url = f"http://{gatekeeper_instance[0]['PublicDnsName']}:5000"
run_benchmark(gatekeeper_url)

time.sleep(25)

print("\n\nRetrieving files")
retrieve_remote_files(bastion_ip, proxy_ip, "temp/tp3-key-pair.pem", "benchmarks_and_logs", [
        "/var/log/proxy_app.log",
        "/tmp/benchmark_proxy_result.txt"
    ])

retrieve_remote_files(bastion_ip, manager_ip, "temp/tp3-key-pair.pem", "benchmarks_and_logs", ["/var/log/sysbench_benchmark.log"])


# Output details
print("\n\n")
print(f"Bastion: {bastion_instance}")
print(f"Gatekeeper: {gatekeeper_instance}")
print(f"Trusted host: {trusted_host_instance}")
print(f"Proxy: {proxy_instance}")
print(f"Workers: {worker_instances}")
print(f"Manager: {manager_instance}")