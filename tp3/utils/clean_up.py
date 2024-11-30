import time

INSTANCE_DELETE_DELAY = 120

def terminate_instances(ec2, instance_ids):
    response = ec2.terminate_instances(InstanceIds=instance_ids)
    return response

def delete_key_pair(ec2, key_name):
    response = ec2.delete_key_pair(KeyName=key_name)
    return response

def delete_security_group(ec2, group_id):
    response = ec2.delete_security_group(GroupId=group_id)
    return response

def clean_up_instances(ec2, instance_ids, key_name, group_id):
    terminate_instances(ec2, instance_ids)
    time.sleep(INSTANCE_DELETE_DELAY)  # We wait to ensure instances are deleted
    delete_key_pair(ec2, key_name)
    time.sleep(60)  # Wait to ensure key pairs are deleted
    delete_security_group(ec2, group_id)  # Ensure instances are deleted before security group
    print("Cleanup completed.")
