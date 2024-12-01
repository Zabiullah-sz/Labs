def get_manager_user_data():
    return """#!/bin/bash
    exec > /var/log/manager_setup.log 2>&1

    # Update the instance
    sudo apt-get update && sudo apt-get upgrade -y

    # Install necessary packages
    sudo apt-get install -y mysql-server wget sysbench python3-pip

    # Configure MySQL to listen on all IPs and set unique server_id
    sudo sed -i 's/bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf
    echo "server-id = 1" | sudo tee -a /etc/mysql/mysql.conf.d/mysqld.cnf
    echo "log_bin = /var/log/mysql/mysql-bin.log" | sudo tee -a /etc/mysql/mysql.conf.d/mysqld.cnf
    sudo systemctl restart mysql
    sudo systemctl enable mysql

    # Set MySQL root password and configure user
    sudo mysql -e 'ALTER USER "root"@"localhost" IDENTIFIED WITH mysql_native_password BY "password123";'
    sudo mysql -u root -ppassword123 -e 'CREATE USER IF NOT EXISTS "root"@"%" IDENTIFIED WITH mysql_native_password BY "password123";'
    sudo mysql -u root -ppassword123 -e 'GRANT ALL PRIVILEGES ON *.* TO "root"@"%";'
    sudo mysql -u root -ppassword123 -e 'FLUSH PRIVILEGES;'

    # Download and set up the Sakila database
    wget https://downloads.mysql.com/docs/sakila-db.tar.gz -P /tmp/
    tar -xzvf /tmp/sakila-db.tar.gz -C /tmp/
    sudo mysql -u root -ppassword123 -e 'CREATE DATABASE IF NOT EXISTS sakila;'
    sudo mysql -u root -ppassword123 sakila < /tmp/sakila-db/sakila-schema.sql
    sudo mysql -u root -ppassword123 sakila < /tmp/sakila-db/sakila-data.sql

    # Run Sysbench benchmark
    sudo sysbench /usr/share/sysbench/oltp_read_only.lua \
        --mysql-db=sakila \
        --mysql-user="root" \
        --mysql-password="password123" prepare

    sudo sysbench /usr/share/sysbench/oltp_read_only.lua \
        --mysql-db=sakila \
        --mysql-user="root" \
        --mysql-password="password123" run \
        > /var/log/sysbench_benchmark.log 2>&1
    """


def get_worker_user_data(manager_ip, server_id):
    return f"""#!/bin/bash
    exec > /var/log/worker_setup.log 2>&1

    # Update the instance
    sudo apt-get update && sudo apt-get upgrade -y

    # Install necessary packages
    sudo apt-get install -y mysql-server wget sysbench python3-pip

    # Configure MySQL to listen on all IPs and set unique server_id
    sudo sed -i 's/bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf
    echo "server-id = {server_id}" | sudo tee -a /etc/mysql/mysql.conf.d/mysqld.cnf
    sudo systemctl restart mysql
    sudo systemctl enable mysql

    # Set MySQL root password
    sudo mysql -e 'ALTER USER "root"@"localhost" IDENTIFIED WITH mysql_native_password BY "password123";'
    sudo mysql -e 'CREATE USER IF NOT EXISTS "root"@"%" IDENTIFIED WITH mysql_native_password BY "password123";'
    sudo mysql -e 'GRANT ALL PRIVILEGES ON *.* TO "root"@"%";'
    sudo mysql -e 'FLUSH PRIVILEGES;'

    # Install Sakila database
    wget https://downloads.mysql.com/docs/sakila-db.tar.gz -P /tmp/
    tar -xzvf /tmp/sakila-db.tar.gz -C /tmp/
    sudo mysql -u root -ppassword123 -e 'CREATE DATABASE IF NOT EXISTS sakila;'
    sudo mysql -u root -ppassword123 sakila < /tmp/sakila-db/sakila-schema.sql
    sudo mysql -u root -ppassword123 sakila < /tmp/sakila-db/sakila-data.sql

    # Configure replication
    sudo mysql -u root -ppassword123 -e 'STOP REPLICA;'
    sudo mysql -u root -ppassword123 -e "CHANGE REPLICATION SOURCE TO \
        SOURCE_HOST='{manager_ip}', \
        SOURCE_USER='root', \
        SOURCE_PASSWORD='password123', \
        SOURCE_PORT=3306;"
    sudo mysql -u root -ppassword123 -e 'START REPLICA;'
    """


def get_proxy_user_data(manager_ip, worker1_ip, worker2_ip):
    with open("utils/proxy_app.py", "r") as script_file:
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


def get_gatekeeper_user_data(trusted_host_ip):
    with open("utils/gatekeeper_app.py", "r") as script_file:
        gatekeeper_app_content = script_file.read()
        # Replace placeholders
        gatekeeper_app_content = gatekeeper_app_content.replace("TRUSTED_HOST_IP", trusted_host_ip)

    return f"""#!/bin/bash
    exec > /var/log/gatekeeper_setup.log 2>&1

    # Update and install necessary packages
    sudo apt-get update && sudo apt-get upgrade -y
    sudo apt-get install -y python3-pip

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
    nohup python3 /home/ubuntu/gatekeeper_app/gatekeeper_app.py &
    """


def get_trusted_host_user_data(proxy_ip):
    with open("utils/trusted_host_app.py", "r") as script_file:
        trusted_host_app_content = script_file.read()
        # Replace placeholders
        trusted_host_app_content = trusted_host_app_content.replace("PROXY_IP", proxy_ip)

    return f"""#!/bin/bash
    exec > /var/log/trusted_host_setup.log 2>&1

    # Update and install necessary packages
    sudo apt-get update && sudo apt-get upgrade -y
    sudo apt-get install -y python3-pip

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
    nohup python3 /home/ubuntu/trusted_host_app/trusted_host_app.py &
    """
