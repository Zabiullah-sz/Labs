def setup_nat_gateway(ec2):
    # Retrieve default VPC
    vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    default_vpc_id = vpcs['Vpcs'][0]['VpcId']
    subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [default_vpc_id]}])['Subnets']
    public_subnet = subnets[0]['SubnetId']
    private_subnet = subnets[1]['SubnetId']
    print(f"Public Subnet: {public_subnet}, Private Subnet: {private_subnet}")

    # Check if NAT Gateway already exists
    existing_nat_gateways = ec2.describe_nat_gateways(
        Filters=[{'Name': 'vpc-id', 'Values': [default_vpc_id]}]
    )['NatGateways']
    if existing_nat_gateways:
        nat_gateway_id = existing_nat_gateways[0]['NatGatewayId']
        print(f"Using existing NAT Gateway: {nat_gateway_id}")
    else:
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

    # Check if route table exists for the private subnet
    route_tables = ec2.describe_route_tables(
        Filters=[{'Name': 'vpc-id', 'Values': [default_vpc_id]}]
    )['RouteTables']
    private_route_table = None
    for route_table in route_tables:
        for association in route_table.get('Associations', []):
            if association.get('SubnetId') == private_subnet:
                private_route_table = route_table['RouteTableId']
                print(f"Using existing route table: {private_route_table}")
                break
        if private_route_table:
            break

    # If no route table exists, create one
    if not private_route_table:
        private_route_table = ec2.create_route_table(VpcId=default_vpc_id)['RouteTable']['RouteTableId']
        ec2.create_route(
            RouteTableId=private_route_table,
            DestinationCidrBlock="0.0.0.0/0",
            NatGatewayId=nat_gateway_id,
        )
        print(f"Created and updated route table: {private_route_table}")

    # Associate route table with private subnet if not already associated
    try:
        ec2.associate_route_table(RouteTableId=private_route_table, SubnetId=private_subnet)
        print(f"Associated route table {private_route_table} with private subnet {private_subnet}")
    except ec2.exceptions.ClientError as e:
        if "Resource.AlreadyAssociated" in str(e):
            print(f"Route table {private_route_table} is already associated with subnet {private_subnet}")
        else:
            raise e

    return public_subnet, private_subnet