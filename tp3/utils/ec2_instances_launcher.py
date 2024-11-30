"""Script to launch EC2 instances."""
def launch_ec2_instance(ec2, 
                    key_pair_name, 
                    security_group_id,
                    instance_type:str = "t2.micro", 
                    num_instances:int = 1, 
                    image_id:str =  "ami-0e86e20dae9224db8",
                    public_ip:bool = False,
                    user_data = "",
                    tag:tuple[str,str] = None,
                    ):
    # Create EC2 client
    # Specify instance parameters
    instance_params = {
        'ImageId': image_id, 
        'InstanceType': instance_type,
        'MinCount': num_instances,
        'MaxCount': num_instances,
        'KeyName': key_pair_name,
        'NetworkInterfaces': [{
            'AssociatePublicIpAddress': public_ip,
            'DeviceIndex': 0,
            'Groups': [security_group_id]
        }],
    }
    if tag is not None:
        instance_params["TagSpecifications"] = [
            {"ResourceType": "instance", "Tags": [{"Key": tag[0], "Value": tag[1]}]}]

    # Launch the instance
    print("Launching instances...")
    response = ec2.run_instances(UserData=user_data, **instance_params)

    # Get the instance ID
    instances_id_and_ip = []
    print("Waiting for instances to be running...")
    for instance in response['Instances']:
        instance_id = instance['InstanceId']
        if not public_ip:
            instances_id_and_ip.append((instance_id, instance["PrivateIpAddress"], None))
        else:
            instances_id_and_ip.append((instance_id, instance["PrivateIpAddress"], instance["PublicDnsName"]))

    print(f"Launched {num_instances} EC2 instances of type {instance_type} with ID and ip: {instances_id_and_ip}")

    return instances_id_and_ip