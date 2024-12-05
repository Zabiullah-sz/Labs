def get_trusted_host_user_data(proxy_ip):
    with open("trusted_host/app.py", "r") as script_file:
        trusted_host_app_content = script_file.read()
        # Replace placeholders
        trusted_host_app_content = trusted_host_app_content.replace("PROXY_IP", proxy_ip)

    return f"""#!/bin/bash
    exec > /var/log/trusted_host_setup.log 2>&1

    # Update and install necessary packages
    sudo apt-get update && sudo apt-get upgrade -y
    sudo apt-get install -y python3-pip

    # Pre-configure answers for iptables-persistent to avoid prompts
    echo iptables-persistent iptables-persistent/autosave_v4 boolean true | sudo debconf-set-selections
    echo iptables-persistent iptables-persistent/autosave_v6 boolean true | sudo debconf-set-selections

    # Install packages non-interactively
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip iptables-persistent netfilter-persistent


    # i got an error without this, probably because flask was not installed correctly
    sudo apt-get remove python3-flask -y
    sudo pip3 install --ignore-installed flask mysql-connector-python requests --break-system-packages

    # Create directories
    mkdir -p /home/ubuntu/trusted_host_app

    # Upload the Flask app
    cat <<EOF > /home/ubuntu/trusted_host_app/trusted_host_app.py
{trusted_host_app_content}
EOF


    # Start the Flask app
    nohup python3 /home/ubuntu/trusted_host_app/trusted_host_app.py > /var/log/trusted_host_app.log 2>&1 &
    """
