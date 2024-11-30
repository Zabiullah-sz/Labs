import boto3

def create_security_group(ec2_client, group_name, group_description, rules=None, vpc_id=None):
    # Check if the security group already exists
    existing_groups = ec2_client.describe_security_groups(
        Filters=[{'Name': 'group-name', 'Values': [group_name]}]
    )['SecurityGroups']

    if existing_groups:
        print(f"Security group '{group_name}' already exists.")
        return existing_groups[0]['GroupId']

    # Get VPC ID
    print(f"Creating security group '{group_name}'...")
    if not vpc_id:
        vpc_id = ec2_client.describe_vpcs()['Vpcs'][0]['VpcId']

    # Create the Security Group
    response = ec2_client.create_security_group(
        GroupName=group_name,
        Description=group_description,
        VpcId=vpc_id
    )
    group_id = response['GroupId']

    # If no rules are provided, skip rule setup here
    if rules:
        print(f"Adding rules to security group '{group_name}'...")
        ec2_client.authorize_security_group_ingress(GroupId=group_id, IpPermissions=rules)
    else:
        print(f"No rules provided. Security group '{group_name}' created with no ingress rules.")

    print(f"Security group '{group_name}' created successfully.")
    return group_id


def ensure_security_group_rules(ec2_client, group_id, desired_rules):
    """
    Ensure that the specified rules exist in the given security group.
    """
    # Fetch existing rules for the security group
    existing_rules = ec2_client.describe_security_groups(GroupIds=[group_id])['SecurityGroups'][0]['IpPermissions']

    # Compare desired rules with existing rules
    for rule in desired_rules:
        if rule not in existing_rules:
            try:
                ec2_client.authorize_security_group_ingress(GroupId=group_id, IpPermissions=[rule])
                print(f"Added missing rule: {rule}")
            except Exception as e:
                print(f"Error adding rule {rule}: {e}")