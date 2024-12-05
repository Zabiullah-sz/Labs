def get_worker_user_data(manager_ip, server_id):
    return f"""#!/bin/bash
    exec > /var/log/worker_setup.log 2>&1

    # Update the instance
    sudo apt-get update && sudo apt-get upgrade -y

    # Install necessary packages
    sudo apt-get install -y mysql-server wget sysbench python3-pip

    # Pre-configure answers for iptables-persistent to avoid prompts
    echo iptables-persistent iptables-persistent/autosave_v4 boolean true | sudo debconf-set-selections
    echo iptables-persistent iptables-persistent/autosave_v6 boolean true | sudo debconf-set-selections

    # Install packages non-interactively
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip iptables-persistent netfilter-persistent


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
