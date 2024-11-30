def get_user_data():
    return """#!/bin/bash
    # Redirect all output to a log file for debugging
    exec > /var/log/setup_sakila.log 2>&1

    # Update the instance
    sudo apt-get update && sudo apt-get upgrade -y

    # Install necessary packages
    sudo apt-get install -y mysql-server wget sysbench python3-pip

    # Install Python dependencies
    sudo pip3 install flask mysql-connector-python requests

    # Configure MySQL to listen on all IPs
    sudo sed -i 's/bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf
    sudo systemctl restart mysql
    sudo systemctl enable mysql

    # Set MySQL root password and create user
    sudo mysql -e 'ALTER USER "root"@"localhost" IDENTIFIED WITH mysql_native_password BY "password123";'
    sudo mysql -u root -ppassword123 -e 'CREATE USER IF NOT EXISTS "root"@"%" IDENTIFIED BY "password123";'
    sudo mysql -u root -ppassword123 -e 'GRANT ALL PRIVILEGES ON *.* TO "root"@"%";'
    sudo mysql -u root -ppassword123 -e 'FLUSH PRIVILEGES;'

    # Download and load the Sakila database
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