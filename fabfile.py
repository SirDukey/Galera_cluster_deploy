# --------------------------------------------------------
# Date: 5-12-2017
# Author: Mike Duke
#
# Fabric file for managing a Galera cluster
# Master is used for admin purpose but can be set to any
# node
#
# --------------------------------------------------------

from fabric.api import run, env, roles, parallel, execute, local, quiet, cd
from fabric.contrib import files
import time

# define roles for all servers and assign a master for admin purposes
env.roledefs = {
    'localhost' : ['127.0.0.1'],
    'master': ['192.168.1.13'],
    'slaves': ['192.168.1.11',
              '192.168.1.12'],
    'nodes': ['192.168.1.11',
              '192.168.1.12',
              '192.168.1.13']
}

env.user = 'root'
env.password = 'supersecret'

# run these functions on the master
@roles('nodes')
def grastate_status():
    '''- Shows if the Galera cluster can be started on the assigned master'''
    run('cat /var/lib/mysql/grastate.dat')

@roles('master')
def grastate_enable():
    '''- Allows the Galera cluster to be started from the assigned master server'''
    run("sed -i 's/safe_to_bootstrap: 0/safe_to_bootstrap: 1/g' /var/lib/mysql/grastate.dat")
    run('cat /var/lib/mysql/grastate.dat')

@roles('master')
def galera_start():
    '''- Initialises the Galera cluster on the assigned master server'''
    run('galera_new_cluster')

@roles('master')
def cluster_status():
    '''- Shows the mysql wsrep size of the Galera cluster'''
    run('echo "SHOW STATUS LIKE \'wsrep_cluster_size\';" | mysql -u root -pglobal01a')

@roles('master')
def vip_status():
    '''- Shows the pacemaker resource status'''
    run('pcs resource show')

@roles('master')
def vip_info():
    '''- Shows information on the floating Virtual_IP pacemaker resource'''
    run('pcs resource show Virtual_IP')

@roles('master')
def pen_status():
    '''- Show the status of the pen load balancing service'''
    run('systemctl status pen')

@roles('master')
def pen_webstats():
    '''- Updates the pen load balancer webstats'''
    run('/var/www/pen/penstats > /dev/null')
    master = env.roledefs['master']
    print 'Load balancing statistics available at:  http://%s/pen/webstats.html' %(master)



# this can be run on all nodes to check the mysql status
@roles('nodes')
@parallel
def mariadb_status():
    '''- Shows the status of mariadb service on all nodes'''
    run('systemctl status mariadb')



@roles('slaves')
@parallel
def mariadb_restart():
    '''- Starts the mariadb service on all slave servers'''
    run('systemctl restart mariadb')

@roles('slaves')
@parallel
def slaves_shutdown():
    '''- Stops the mariadb server and sends shutdown signal to all slave servers'''
    run('systemctl stop mariadb')
    run('poweroff')
    
@roles('master')
def master_shutdown():
    '''- Stops the mariadb service and sends shutdown signal to the assigned master server'''
    run('systemctl stop mariadb')
    run('poweroff')

@roles('localhost')
def nodes_status():
    '''- Pings all the nodes from localhost to check if they are online/offline'''
    with quiet():
        for node in env.roledefs['nodes']:
            if local('ping -c1 -W2 %s' %(node)).succeeded:
                print '%s Online' %(node)
            else:
                print '%s Offline' %(node)



@roles('master')
def mysql_tuner():
    '''- Installs git and MySQLTuner, then runs the application on the assigned master'''
    if files.exists('/bin/git'):
        if files.exists('/root/MySQLTuner-perl/mysqltuner.pl'):
            with cd('/root/MySQLTuner-perl/'):
                run('perl mysqltuner.pl --user root --pass=Al0^0M0r@')
        else:
            with cd('/root/'):    
                run('git clone https://github.com/major/MySQLTuner-perl.git')
            with cd('/root/MySQLTuner-perl/'):
                run('perl mysqltuner.pl --user root --pass=Al0^0M0r@')

    else:
        run('yum -y install git')
        if files.exists('/root/MySQLTuner-perl/mysqltuner.pl'):
            with cd('/root/MySQLTuner-perl/'):
                run('perl mysqltuner.pl --user root --pass=Al0^0M0r@')
        else:
            with cd('/root/'):
                run('git clone https://github.com/major/MySQLTuner-perl.git')
            with cd('/root/MySQLTuner-perl/'):
                run('perl mysqltuner.pl --user root --pass=Al0^0M0r@')

    

@roles('master')
def show_db_sizes():
    '''- Displays the sizes of the db's'''
    run('du -hs /var/lib/mysql/')



@roles('master')
def list_databases():
    '''- List all the databases'''
    run('echo "SHOW DATABASES;" | mysql -u root -pglobal01a')



@roles('nodes')
def install_mariadb():
    '''- Install MariaDB-server on all nodes'''
    run('touch /etc/yum.repos.d/MariaDB.repo')
    files.append('/etc/yum.repos.d/MariaDB.repo', '[mariadb]\nname = MariaDB\nbaseurl = http://yum.mariadb.org/10.2/centos7-amd64\ngpgkey=https://yum.mariadb.org/RPM-GPG-KEY-MariaDB\ngpgcheck=1', use_sudo=False, partial=False, escape=True, shell=True)
    files.append('/etc/hosts', '192.168.1.11    novsqlclus1-node1\n192.168.1.12    novsqlclus1-node2\n192.168.1.13    novsqlclus1-node3', use_sudo=False, partial=False, escape=True, shell=False)
    run('yum repolist')
    run('yum -y install MariaDB-server')
    run('systemctl start mysql')
    run('mysql_secure_installation')



@roles('nodes')
def configure_cluster():
    '''- Configure the Galera cluster'''
    for node in env.roledefs['nodes']:
        node_name = run("getent hosts", node, "| awk '{ print $2 }'")
        run('touch /etc/my.cnf.d/server.cnf')
        files.append('/etc/my.cnf.d/server.cnf', 'wsrep_on=ON\nwsrep_provider=/usr/lib64/galera/libgalera_smm.so\nwsrep_cluster_address="gcomm://192.168.1.11,192.168.1.12,192.168.1.13"\nwsrep_cluster_name="galera_cluster"\nwsrep_node_address="' + node + '"\nwsrep_node_name="'+ node_name + '"\nwsrep_sst_method=rsync', use_sudo=False, partial=False, escape=True, shell=False)



@roles('nodes')
def install_veeam():
    '''- Install the Veeam agent on all nodes'''
    run('yum -y install veeam')



@parallel
@roles('nodes')
def install_zabbix_agent():
    '''- Install Zabbix agent 3.2 on all nodes'''
    run('rpm -Uvh http://repo.zabbix.com/zabbix/3.2/rhel/7/x86_64/zabbix-release-3.2-1.el7.noarch.rpm')
    run('yum repolist')
    run('yum install -y zabbix-agent')



@parallel
@roles('nodes')
def configure_zabbix_agent():
    '''- Configure the Zabbix agent conf file'''
    hostname = run('hostname')
    run("sed -i 's/Server=127.0.0.1/Server=192.168.1.21/g' /etc/zabbix/zabbix_agentd.conf")
    run("sed -i 's/ServerActive=127.0.0.1/ServerActive=/g' /etc/zabbix/zabbix_agentd.conf")
    run("sed -i 's/Hostname=Zabbix server/Hostname=" + hostname + "/g' /etc/zabbix/zabbix_agentd.conf")


@parallel
@roles('nodes')
def start_zabbix_agent():
    '''- Starts the Zabbix agent service on all nodes'''
    with quiet():
        run('systemctl start zabbix-agent')
        run('systemctl enable zabbix-agent')
        hostname = run('hostname')
        state = run("systemctl list-units | grep zabbix-agent | awk '{ print $4 }'")
        print hostname, 'agent:', state


@roles('master')
def show_node_hostnames():
    '''- Display the hostnames from the Master node'''
    node_list = env.roledefs['nodes']
    node_name = run("getent hosts", node_list[0], "| awk NR > 2'{ print $2 }'")
    print node_name


@parallel
@roles('nodes')
def install_mytop():
    try:
        run('yum install -y mytop')
        print('Done!')
    except:
        print('error')



# -------------------------------------------------------------
# These are the main functions to start/stop/deploy the Galera cluster
# -------------------------------------------------------------
def start_cluster():
    '''> Starts the Galera cluster'''
    execute(grastate_enable)
    execute(galera_start)
    time.sleep(5)
    execute(mysql_restart)
    execute(cluster_status)
    print 'Galera cluster started'

def shutdown_cluster():
    '''> Shuts down the Galera cluster'''
    with quiet():
        execute(slaves_shutdown)
        time.sleep(5)
        execute(master_shutdown)
        time.sleep(5)
        execute(nodes_status)
        print 'Galera cluster has been shut down successfully'

def deploy_cluster():
    '''> Deploy a Galera cluster'''
    execute(install_mariadb)
    execute(configure_cluster)
    execute(start_cluster)
    print 'Galera cluster has been deployed'

