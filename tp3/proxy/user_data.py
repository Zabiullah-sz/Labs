def get_proxy_user_data(manager_ip, worker1_ip, worker2_ip):
    with open("proxy/app.py", "r") as script_file:
        proxy_app_content = script_file.read()
        # Replace placeholders
        proxy_app_content = proxy_app_content.replace("MANAGER_IP", manager_ip)
        proxy_app_content = proxy_app_content.replace("WORKER1_IP", worker1_ip)
        proxy_app_content = proxy_app_content.replace("WORKER2_IP", worker2_ip)

    return f"""#!/bin/bash
    exec > /var/log/proxy_setup.log 2>&1

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
    mkdir -p /home/ubuntu/proxy_app

    # Upload the Flask app
    cat <<EOF > /home/ubuntu/proxy_app/proxy_app.py
{proxy_app_content}
EOF

    # Start the Flask app
    nohup python3 /home/ubuntu/proxy_app/proxy_app.py > /var/log/proxy_app.log 2>&1 &
    """
