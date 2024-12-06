import paramiko
import time
import socket
import os


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
    
def generate_iptables_command(source_ip, port=5000):
    """
    Generate iptables rules to allow traffic only from a specific source IP and block all others.
    """
    return f"""

        sudo iptables -F  # Flush existing rules
        sudo iptables -A INPUT -p tcp --dport {port} -s {source_ip} -j ACCEPT
        sudo iptables -A INPUT -p tcp --dport {port} -j DROP  # Drop all other traffic on port 5000
        sudo iptables -A INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT  # Allow established connections
        sudo netfilter-persistent save


    """


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




def retrieve_remote_files(bastion_ip, target_ip, key_path, local_dir, remote_files):
    """
    Retrieve remote files from a target instance via a Bastion Host and save them locally.

    Parameters:
        bastion_ip (str): Public IP or DNS of the Bastion Host.
        target_ip (str): Private IP of the target instance to retrieve files from.
        key_path (str): Path to the SSH private key for authentication.
        remote_files (list): List of remote file paths to retrieve.
        local_dir (str): Local directory where files will be saved.

    Returns:
        None
    """
    ssh = establish_ssh_via_bastion(bastion_ip, target_ip, key_path)

    if ssh:
        # Ensure the local directory exists
        os.makedirs(local_dir, exist_ok=True)

        for remote_file in remote_files:
            # Use SCP to fetch the file
            local_file_path = os.path.join(local_dir, os.path.basename(remote_file))
            try:
                print(f"Retrieving {remote_file} from {target_ip}...")
                sftp = ssh.open_sftp()
                sftp.get(remote_file, local_file_path)
                sftp.close()
                print(f"Successfully retrieved {remote_file} to {local_file_path}")
            except Exception as e:
                print(f"Error retrieving {remote_file}: {e}")

        # Close the SSH connection
        ssh.close()
    else:
        print(f"Failed to establish SSH connection to {target_ip}.")
