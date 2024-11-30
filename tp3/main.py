import boto3
import time
from utils.create_security_group import create_security_group
from utils.ec2_instances_launcher import launch_ec2_instance
from utils.create_key_pair import generate_key_pair
from dotenv import load_dotenv
from utils.user_data import get_user_data
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
ec2.authorize_security_group_ingress(
    GroupId=private_sg_id,
    IpPermissions=[
        {
            'IpProtocol': 'tcp',
            'FromPort': 3306,  # Example: MySQL
            'ToPort': 3306,
            'UserIdGroupPairs': [{'GroupId': private_sg_id}]  # Allow internal communication
        }
    ]
)

# Add rules to allow communication from public SG to private SG
ec2.authorize_security_group_ingress(
    GroupId=private_sg_id,
    IpPermissions=[
        {
            'IpProtocol': 'tcp',
            'FromPort': 3306,  # Example: MySQL
            'ToPort': 3306,
            'UserIdGroupPairs': [{'GroupId': public_sg_id}]  # Allow Gateway to access private group
        }
    ]
)


# Step 5: Launch Instances
print("Launching instances...")

# Gateway with public IP
gateway_instance = launch_ec2_instance(
    ec2,
    key_pair_name=KEY_PAIR_NAME,
    security_group_id=public_sg_id,
    public_ip=True,  # Assign public IP
    tag=("Name", "Gateway"),
)


trusted_host_instance = launch_ec2_instance(
    ec2,
    key_pair_name="tp3-key-pair",
    security_group_id=public_sg_id,  # Security group restricts access to Gatekeeper
    public_ip=True,  # No public IP
    tag=("Name", "TrustedHost"),
)

proxy_instance = launch_ec2_instance(
    ec2,
    key_pair_name="tp3-key-pair",
    security_group_id=public_sg_id,  # Security group allows access from Trusted Host
    public_ip=True,  # No public IP
    tag=("Name", "Proxy"),
)

manager_instance = launch_ec2_instance(
    ec2,
    key_pair_name="tp3-key-pair",
    security_group_id=public_sg_id,  # Security group allows access from Proxy
    public_ip=True,  # No public IP
    user_data=get_user_data(),
    tag=("Name", "Manager"),
)

worker_instances = launch_ec2_instance(
    ec2,
    key_pair_name="tp3-key-pair",
    security_group_id=public_sg_id,  # Security group allows access from Proxy
    public_ip=True,  # No public IP
    tag=("Name", "Worker"),
    user_data=get_user_data(),
    num_instances=2,
)

# Output details
print(f"Gateway: {gateway_instance}")
print(f"Manager: {manager_instance}")
print(f"Workers: {worker_instances}")
print(f"Proxy: {proxy_instance}")

# Step 6: Clean Up (Optional)
# Uncomment to clean up resources
# print("\nCleaning up resources...")
# instance_ids = [
#     gateway_instance[0][0],
#     manager_instance[0][0],
#     *[w[0] for w in worker_instances],
#     proxy_instance[0][0],
# ]
# clean_up(ec2, instance_ids, KEY_PAIR_NAME, public_sg_id)
