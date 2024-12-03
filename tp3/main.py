import boto3
import time
from _utils.create_security_group import create_security_group, ensure_security_group_rules
from _utils.ec2_instances_launcher import launch_ec2_instance
from _utils.create_key_pair import generate_key_pair
from dotenv import load_dotenv
from gatekeeper.user_data import get_gatekeeper_user_data
from _utils.benchmarking import run_benchmark
from _utils.run_command_instance import establish_ssh_via_bastion, run_command
from trusted_host.user_data import get_trusted_host_user_data
from manager.user_data import get_manager_user_data
from workers.user_data import get_worker_user_data
from proxy.user_data import get_proxy_user_data
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
            'ToPort': 5000,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        },
        {
            'IpProtocol': 'tcp',
            'FromPort': 443,
            'ToPort': 443,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        },
        {
            'IpProtocol': 'icmp',
            'FromPort': -1,
            'ToPort': -1,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
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
            'IpRanges': [{'CidrIp': '172.31.0.0/16'}]
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

# Step 4.1: Setup NAT Gateway
def setup_nat_gateway(ec2):
    # Retrieve default VPC
    vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    default_vpc_id = vpcs['Vpcs'][0]['VpcId']
    subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [default_vpc_id]}])['Subnets']
    public_subnet = subnets[0]['SubnetId']
    private_subnet = subnets[1]['SubnetId']
    print(f"Public Subnet: {public_subnet}, Private Subnet: {private_subnet}")

    # Allocate Elastic IP for NAT Gateway
    eip = ec2.allocate_address(Domain="vpc")
    eip_allocation_id = eip['AllocationId']
    print(f"Elastic IP: {eip['PublicIp']}")

    # Create NAT Gateway
    nat_gateway = ec2.create_nat_gateway(SubnetId=public_subnet, AllocationId=eip_allocation_id)
    nat_gateway_id = nat_gateway['NatGateway']['NatGatewayId']
    print(f"Created NAT Gateway: {nat_gateway_id}")

    # Wait for NAT Gateway
    ec2.get_waiter('nat_gateway_available').wait(NatGatewayIds=[nat_gateway_id])

    # Configure private route table
    private_route_table = ec2.create_route_table(VpcId=default_vpc_id)['RouteTable']['RouteTableId']
    ec2.create_route(
        RouteTableId=private_route_table,
        DestinationCidrBlock="0.0.0.0/0",
        NatGatewayId=nat_gateway_id,
    )
    ec2.associate_route_table(RouteTableId=private_route_table, SubnetId=private_subnet)
    print(f"Private route table associated with: {private_subnet}")

    return public_subnet, private_subnet


print("Setting up NAT Gateway...")
public_subnet, private_subnet = setup_nat_gateway(ec2)

# Step 5: Launch Instances
print("Launching instances...")

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

# Proxy Instance
proxy_instance = launch_ec2_instance(
    ec2,
    key_pair_name=KEY_PAIR_NAME,
    security_group_id=private_sg_id,
    public_ip=False,
    subnet_id=private_subnet,
    user_data=get_proxy_user_data(manager_ip, worker_instances[0][0]["PrivateIpAddress"], worker_instances[1][0]["PrivateIpAddress"]),
    tag=("Name", "Proxy"),
)

# Trusted Host
trusted_host_instance = launch_ec2_instance(
    ec2,
    key_pair_name=KEY_PAIR_NAME,
    security_group_id=private_sg_id,
    public_ip=False,
    subnet_id=private_subnet,
    user_data=get_trusted_host_user_data(proxy_instance[0]["PrivateIpAddress"]),
    tag=("Name", "TrustedHost"),
)

# Gatekeeper
gatekeeper_instance = launch_ec2_instance(
    ec2,
    key_pair_name=KEY_PAIR_NAME,
    security_group_id=public_sg_id,
    public_ip=True,
    subnet_id=public_subnet,
    user_data=get_gatekeeper_user_data(trusted_host_instance[0]["PrivateIpAddress"]),
    tag=("Name", "Gatekeeper"),
)

print("All instances launched.")


# sleep for 4 minutes to allow instances to be ready, make it with a loop so we know the progress after every minute
for i in range(4):
    print(f"Waiting for instances to be ready... {i+1}/8")
    time.sleep(60)


bastion_ip = bastion_instance[0]["PublicDnsName"]
proxy_ip = proxy_instance[0]["PrivateIpAddress"]

ssh = establish_ssh_via_bastion(bastion_ip, proxy_ip, "temp/tp3-key-pair.pem")

if ssh:
    # Define the remote log file paths and the local destination directory
    log_files = ["/var/log/proxy_app.log", "/var/log/proxy_setup.log"]
    local_log_dir = "logs"

    # Ensure the local directory exists
    os.makedirs(local_log_dir, exist_ok=True)

    for log_file in log_files:
        # Use SCP to fetch the log file
        local_file_path = os.path.join(local_log_dir, os.path.basename(log_file))
        try:
            print(f"Retrieving {log_file} from proxy...")
            sftp = ssh.open_sftp()
            sftp.get(log_file, local_file_path)
            sftp.close()
            print(f"Successfully retrieved {log_file} to {local_file_path}")
        except Exception as e:
            print(f"Error retrieving {log_file}: {e}")
    
    # Optionally, test the connection
    command = "echo 'Testing connection to proxy instance' > /home/ubuntu/test.txt"
    output, error = run_command(ssh, command)
    print(f"Output: {output}, Error: {error}")

    # Close the SSH connection
    ssh.close()
else:
    print("Failed to establish SSH connection to the proxy.")


# Output details
print(f"Gatekeeper: {gatekeeper_instance}")
print(f"Manager: {manager_instance}")
print(f"Workers: {worker_instances}")
print(f"Proxy: {proxy_instance}")


# gateKeeper_PublicDns = gatekeeper_instance[0]["PublicDnsName"]

# # Fetch Gatekeeper public DNS
# gatekeeper_dns = gatekeeper_instance[0]["PublicDnsName"]
# gatekeeper_url = f"http://{gatekeeper_dns}:5000"

# Call benchmarking function
print("\nStarting benchmarking...")
# run_benchmark(gatekeeper_url)



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
