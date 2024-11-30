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
    return f"""#!/bin/bash
    exec > /var/log/proxy_setup.log 2>&1

    # Update and install necessary packages
    sudo apt-get update && sudo apt-get upgrade -y
    sudo apt-get install -y python3-pip

    # Install Flask and dependencies
    sudo pip3 install flask mysql-connector-python requests

    # Create proxy application
    cat <<EOF > /home/ubuntu/proxy_app.py
    from flask import Flask, request, jsonify
    import random
    import mysql.connector

    app = Flask(__name__)

    MANAGER_DB = {{"host": "{manager_ip}", "user": "root", "password": "password123", "database": "sakila"}}
    WORKER_DBS = [
        {{"host": "{worker1_ip}", "user": "root", "password": "password123", "database": "sakila"}},
        {{"host": "{worker2_ip}", "user": "root", "password": "password123", "database": "sakila"}}
    ]

    def execute_query(db_config, query):
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        conn.close()
        return result

    @app.route('/query', methods=['POST'])
    def route_request():
        data = request.get_json()
        query_type = data.get("type", "read").lower()
        query = data.get("query", "")

        if query_type == "write":
            result = execute_query(MANAGER_DB, query)
        elif query_type == "read":
            worker_db = random.choice(WORKER_DBS)
            result = execute_query(worker_db, query)
        else:
            return jsonify({{"error": "Invalid query type"}}), 400

        return jsonify({{"result": result}})

    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000)
    EOF

    nohup python3 /home/ubuntu/proxy_app.py &
    """


def get_gatekeeper_user_data(trusted_host_ip):
    return f"""#!/bin/bash
    exec > /var/log/gatekeeper_setup.log 2>&1

    # Update and install necessary packages
    sudo apt-get update && sudo apt-get upgrade -y
    sudo apt-get install -y python3-pip

    # Install Flask
    sudo pip3 install flask requests

    # Create gatekeeper application
    cat <<EOF > /home/ubuntu/gatekeeper_app.py
    from flask import Flask, request, jsonify
    import requests

    app = Flask(__name__)

    TRUSTED_HOST_URL = "http://{trusted_host_ip}:5000"

    @app.route('/validate', methods=['POST'])
    def validate_request():
        data = request.get_json()
        if "query" not in data:
            return jsonify({{"error": "Invalid request"}}), 400

        response = requests.post(TRUSTED_HOST_URL, json=data)
        return response.json()

    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=80)
    EOF

    nohup python3 /home/ubuntu/gatekeeper_app.py &
    """


def get_trusted_host_user_data(proxy_ip):
    return f"""#!/bin/bash
    exec > /var/log/trusted_host_setup.log 2>&1

    # Update and install necessary packages
    sudo apt-get update && sudo apt-get upgrade -y
    sudo apt-get install -y python3-pip

    # Install Flask
    sudo pip3 install flask requests

    # Create trusted host application
    cat <<EOF > /home/ubuntu/trusted_host_app.py
    from flask import Flask, request, jsonify
    import requests

    app = Flask(__name__)

    PROXY_URL = "http://{proxy_ip}:5000"

    @app.route('/', methods=['POST'])
    def forward_request():
        data = request.get_json()
        response = requests.post(PROXY_URL + "/query", json=data)
        return response.json()

    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000)
    EOF

    nohup python3 /home/ubuntu/trusted_host_app.py &
    """
