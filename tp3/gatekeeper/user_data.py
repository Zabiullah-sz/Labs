def get_gatekeeper_user_data(trusted_host_ip):
    with open("gatekeeper/app.py", "r") as script_file:
        gatekeeper_app_content = script_file.read()
        # Replace placeholders
        gatekeeper_app_content = gatekeeper_app_content.replace("TRUSTED_HOST_IP", trusted_host_ip)

    return f"""#!/bin/bash
    exec > /var/log/gatekeeper_setup.log 2>&1

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
    mkdir -p /home/ubuntu/gatekeeper_app

    # Upload the Flask app
    cat <<EOF > /home/ubuntu/gatekeeper_app/gatekeeper_app.py
{gatekeeper_app_content}
EOF

    # Start the Flask app
    nohup python3 /home/ubuntu/gatekeeper_app/gatekeeper_app.py > /var/log/gatekeeper_app.log 2>&1 &
    """
