import boto3
import time
from utils.create_security_group import create_security_group, ensure_security_group_rules
from utils.ec2_instances_launcher import launch_ec2_instance
from utils.create_key_pair import generate_key_pair
from dotenv import load_dotenv
from utils.user_data import get_worker_user_data, get_manager_user_data, get_proxy_user_data, get_gatekeeper_user_data, get_trusted_host_user_data
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
print("Creating security groups...")
public_sg_id = create_security_group(
    ec2_client=ec2,
    group_name="public-sg",
    group_description="Public Security Group",
    rules=[
        {
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]  # Allow SSH
        },
        {
            'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]  # Allow HTTP
        },
        {
            "IpProtocol": "tcp",
            "FromPort": 3306,
            "ToPort": 3306,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        },

        {
            'IpProtocol': 'tcp',
            'FromPort': 443,
            'ToPort': 443,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]  # Allow HTTPS
        },
        {
            'IpProtocol': 'icmp',
            'FromPort': -1,
            'ToPort': -1,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]  # Allow ICMP
        }
    ]
)



private_sg_id = create_security_group(
    ec2_client=ec2,
    group_name="private-sg",
    group_description="Private Security Group",
)

print("Modifying rules")

# Add rules to allow communication between private instances
desired_private_rules = [
    {
        'IpProtocol': 'tcp',
        'FromPort': 3306,  # Example: MySQL
        'ToPort': 3306,
        'UserIdGroupPairs': [{'GroupId': private_sg_id}]  # Allow internal communication
    }
]
ensure_security_group_rules(ec2, private_sg_id, desired_private_rules)

# Add rules to allow communication from public SG to private SG
desired_public_rules = [
    {
        'IpProtocol': 'tcp',
        'FromPort': 3306,  # Example: MySQL
        'ToPort': 3306,
        'UserIdGroupPairs': [{'GroupId': public_sg_id}]  # Allow Gatekeeper to access private group
    }
]
ensure_security_group_rules(ec2, private_sg_id, desired_public_rules)


# Step 5: Launch Instances
print("Launching instances...")

manager_instance = launch_ec2_instance(
    ec2,
    key_pair_name="tp3-key-pair",
    security_group_id=public_sg_id,  # Security group allows access from Proxy
    public_ip=True,  # No public IP
    user_data=get_manager_user_data(),
    tag=("Name", "Manager"),
)

manager_ip = manager_instance[0]["PrivateIpAddress"]

# Launch Workers with unique server_ids
worker_instances = []

for i in range(2):  # Assuming 2 workers
    server_id = i + 2  # Manager is 1; workers start from 2
    worker = launch_ec2_instance(
        ec2,
        key_pair_name="tp3-key-pair",
        security_group_id=public_sg_id,  # Security group allows access from Proxy
        public_ip=True,  # Public IP for testing
        user_data=get_worker_user_data(manager_ip, server_id),
        tag=("Name", f"Worker-{server_id}"),
    )
    worker_instances.append(worker)

# Extract worker private IPs
worker_ips = [worker[0]["PrivateIpAddress"] for worker in worker_instances]
worker1_ip, worker2_ip = worker_ips


proxy_instance = launch_ec2_instance(
    ec2,
    key_pair_name="tp3-key-pair",
    security_group_id=public_sg_id,  # Security group allows access from Trusted Host
    public_ip=True,  # No public IP
    user_data=get_proxy_user_data(manager_ip, worker1_ip, worker2_ip),
    tag=("Name", "Proxy"),
)

proxy_ip = proxy_instance[0]["PrivateIpAddress"]

trusted_host_instance = launch_ec2_instance(
    ec2,
    key_pair_name="tp3-key-pair",
    security_group_id=public_sg_id,  # Security group restricts access to Gatekeeper
    public_ip=True,  # No public IP
    user_data=get_trusted_host_user_data(proxy_ip),
    tag=("Name", "TrustedHost"),
)

trusted_host_ip = trusted_host_instance[0]["PrivateIpAddress"]


# Gatekeeper with public IP
gatekeeper_instance = launch_ec2_instance(
    ec2,
    key_pair_name=KEY_PAIR_NAME,
    security_group_id=public_sg_id,
    public_ip=True,  # Assign public IP
    user_data=get_gatekeeper_user_data(trusted_host_ip),
    tag=("Name", "Gatekeeper"),
)

# Output details
print(f"Gatekeeper: {gatekeeper_instance}")
print(f"Manager: {manager_instance}")
print(f"Workers: {worker_instances}")
print(f"Proxy: {proxy_instance}")

# Step 6: Clean Up (Optional)
# Uncomment to clean up resources
# print("\nCleaning up resources...")
# instance_ids = [
#     gatekeeper_instance[0][0],
#     manager_instance[0][0],
#     *[w[0] for w in worker_instances],
#     proxy_instance[0][0],
# ]
# clean_up(ec2, instance_ids, KEY_PAIR_NAME, public_sg_id)
