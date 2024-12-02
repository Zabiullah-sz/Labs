import paramiko
import time
import socket


def establish_ssh_connection(public_ip, key_pair_path, retries=5):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    for attempt in range(retries):
        try:
            print(f"Attempt {attempt + 1} to connect to {public_ip}")
            # Connect to the instance with increased timeout
            ssh.connect(hostname=public_ip, username='ubuntu', key_filename=key_pair_path, timeout=90)
            print("Connection established")
            return ssh  # Return the SSH client object for reuse
        except paramiko.ssh_exception.SSHException as e:
            print(f"SSHException occurred: {e}")
            time.sleep(30)  # Wait before retrying
        except socket.timeout as e:
            print(f"Socket timeout occurred: {e}")
            time.sleep(30)  # Wait before retrying
    return None  # Return None if connection failed after retries
def run_command(ssh, command):
    try:
        # Execute the command using the provided SSH connection
        stdin, stdout, stderr = ssh.exec_command(command)
        # Get the output
         # Try to decode with UTF-8 first
        try:
            output = stdout.read().decode('utf-8').strip()
        except UnicodeDecodeError:
            # If UTF-8 decoding fails, try ISO-8859-1 (Latin-1)
            output = stdout.read().decode('ISO-8859-1').strip()

        # Get the error output similarly
        try:
            error = stderr.read().decode('utf-8').strip()
        except UnicodeDecodeError:
            error = stderr.read().decode('ISO-8859-1').strip()

        return output, error
    except paramiko.SSHException as e:
        print(f"SSHException occurred while executing the command: {e}")
        return None, str(e)
    

def establish_ssh_via_bastion(bastion_ip, private_ip, key_pair_path, retries=5):
    bastion_ssh = paramiko.SSHClient()
    bastion_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Connect to the Bastion Host
    for attempt in range(retries):
        try:
            print(f"Connecting to Bastion Host at {bastion_ip}")
            bastion_ssh.connect(hostname=bastion_ip, username='ubuntu', key_filename=key_pair_path, timeout=90)
            print("Bastion connection established")
            break
        except Exception as e:
            print(f"Failed to connect to bastion: {e}")
            time.sleep(30)
    else:
        return None  # Failed to connect to bastion

    # Create a new SSH transport channel
    transport = bastion_ssh.get_transport()
    channel = transport.open_channel(
        "direct-tcpip", (private_ip, 22), (bastion_ip, 22)
    )

    # Connect to the private instance via the bastion
    private_ssh = paramiko.SSHClient()
    private_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for attempt in range(retries):
        try:
            print(f"Connecting to Private Instance at {private_ip} via Bastion")
            private_ssh.connect(
                hostname=private_ip,
                username="ubuntu",
                key_filename=key_pair_path,
                sock=channel
            )
            print("Private instance connection established")
            return private_ssh
        except Exception as e:
            print(f"Failed to connect to private instance: {e}")
            time.sleep(30)
    return None
