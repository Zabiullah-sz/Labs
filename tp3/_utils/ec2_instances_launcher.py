def launch_ec2_instance(ec2, 
                        key_pair_name, 
                        security_group_id,
                        instance_type="t2.micro", 
                        num_instances=1, 
                        image_id="ami-0e86e20dae9224db8",
                        public_ip=False,
                        user_data="",
                        subnet_id=None,  # Add subnet_id as a parameter
                        tag=None):
    """
    Launch EC2 instances and return their details.
    
    Returns:
        List of dictionaries with Instance ID, Private IP, and Public DNS (if applicable).
    """
    # Define instance parameters
    instance_params = {
        'ImageId': image_id, 
        'InstanceType': instance_type,
        'MinCount': num_instances,
        'MaxCount': num_instances,
        'KeyName': key_pair_name,
        'NetworkInterfaces': [{
            'AssociatePublicIpAddress': public_ip,
            'DeviceIndex': 0,
            'Groups': [security_group_id],
        }],
    }

    # Add subnet_id to the NetworkInterfaces if specified
    if subnet_id:
        instance_params['NetworkInterfaces'][0]['SubnetId'] = subnet_id

    if tag is not None:
        instance_params["TagSpecifications"] = [
            {"ResourceType": "instance", "Tags": [{"Key": tag[0], "Value": tag[1]}]}]

    # Launch instances
    print("Launching instances...")
    response = ec2.run_instances(UserData=user_data, **instance_params)

    # Collect instance IDs
    instance_ids = [instance['InstanceId'] for instance in response['Instances']]
    print(f"Instances launched with IDs: {instance_ids}")

    # Wait for instances to be running
    print("Waiting for instances to be running...")
    ec2.get_waiter('instance_running').wait(InstanceIds=instance_ids)

    # Fetch instance details
    print("Fetching instance details...")
    instances_info = ec2.describe_instances(InstanceIds=instance_ids)['Reservations']

    # Extract details
    instances_details = []
    for reservation in instances_info:
        for instance in reservation['Instances']:
            details = {
                "InstanceId": instance['InstanceId'],
                "PrivateIpAddress": instance.get("PrivateIpAddress"),
                "PublicDnsName": instance.get("PublicDnsName") if public_ip else None
            }
            instances_details.append(details)

    print(f"Launched instances details: {instances_details}")
    return instances_details
