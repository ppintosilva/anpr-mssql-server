#!/usr/bin/env python
# -*- coding: utf-8 -*-

from subprocess import call
import os
import stat
import click
import docker
import ast
import sys

###############################################
#
#
#   Global Variables / Config
#
#
###############################################

image_name = "microsoft/mssql-server-linux"
container_name = "anpr-mssql-server"

dbfiles_path = os.getcwd() + "/dbfiles"
bakfile_path = os.getcwd() + "/bakfile"

dbfiles_container_path = '/mnt/anpr-mssql'
bakfile_container_path = '/mnt/anpr-bak'

default_db_namemap = {'CortexDBWarehouse' : 'CortexDBWarehouse_Primary.mdf',
                      'BLOB' : 'CortexDBWarehouse_BLOB.mdf',
                      'DATA' : 'CortexDBWarehouse_DATA.mdf',
                      'INDEX' : 'CortexDBWarehouse_INDEX.mdf',
                      'CortexDBWarehouse_log' : 'CortexDBWarehouse_Log.ldf'}

###############################################
#
#
#   Queries
#
#
###############################################

def query_restoredb_builder(dbname, db_namemap, bakfile_name): 
    move_lines = ""
    for dbComponent, componentFilename in db_namemap.iteritems():
        move_lines += "MOVE ''{}'' TO ''{}'', ".format(
                dbComponent, 
                "{}/{}".format(dbfiles_container_path,componentFilename))
    move_lines += "STATS = 10"
    sql_function = " ".join(["RESTORE DATABASE {}".format(dbname),
                            "FROM DISK = ''{}''".format("{}/{}".format(bakfile_container_path, bakfile_name)),
                            "WITH {}".format(move_lines)])
    return "\n".join(["USE master",
                      "GO",
                      "EXEC('{}')".format(sql_function),
                      "GO"])

def query_attachdb_builder(dbname, db_namemap):
    filenames = list(db_namemap.values())
    filename_lines = ""
    for i in range(0, len(filenames), 1):
        if i == len(filenames)-1:
            separator = ';'
        else:
            separator = ','
        filename_lines += "@filename{} = \"{}\"{} ".format(i+1, "".join([dbfiles_container_path, "/", filenames[i]]), separator)

    return " ".join(["EXEC sp_attach_db @dbname ='{}',".format(dbname),
                     filename_lines])

def query_restore_progress_builder():
    return "SET NOCOUNT ON;SELECT start_time,cast(percent_complete as int) as progress,dateadd(second,estimated_completion_time/1000, getdate()) as estimated_completion_time, cast(estimated_completion_time/1000/60 as int) as minutes_left FROM sys.dm_exec_requests r WHERE r.command='RESTORE DATABASE'"

###############################################
#
#
#   Helpers
#
#
###############################################

def getContainer():
    client = docker.from_env()
    try:
        return client.containers.get(container_name)
    except docker.errors.NotFound as e:
        # click.echo(e)
        return None
    except docker.errors.APIError as e2:
    #    click.echo(e2)
        return None

###############################################
#
#
#   Command Line Interface
#
#
###############################################

@click.group(help="This is a wrapper application to ease the setup and management of the automatic number plate recognition (ANPR) microsoft sql-server database")
def anpr():
    pass

@anpr.command(name='ls-volumes', short_help="List block devices")
def lsvolumes():
    """
    List block devices

    This operation is meant to help the user determining the block device which the openstack volume has been attached.
    """
    call(["lsblk", "-o", "NAME,FSTYPE,SIZE,MOUNTPOINT"])

@anpr.command('mount', short_help="Mount the anpr database files")
@click.argument('volume-path', required = True, type=click.Path(exists=True))
@click.argument('mssql-file-format', required = True, type = click.Choice(['bak', 'mdf']))
def mount(volume_path, mssql_file_format):
    """
    Mount the openstack volume containing the bak or mdf files.

    This operation takes as input the uuid of the block device corresponding to the openstack volume, which can be determined through the use of 'ls-disks' and 'ls-uuids' operations. The disk will be mounted on subdirectories 'bakfile' or 'dbfiles' depending on the format of the anpr data held by the openstack volume. If the anpr data consists of a backup restore file then it will be mounted in 'bakfile', otherwise if it consists of master and log database files, it will be mounted in 'dbfiles'. This behavior must specified in second parameter by passing one of the following values {'bak', 'mdf'}, respectively.

    Sudo permissions are required. If user does not have passwordless sudo it will prompt for a password.
    """
    if mssql_file_format == 'mdf':
        target_dir = dbfiles_path
    else:
        target_dir = bakfile_path
    if stat.S_ISBLK(os.stat(volume_path).st_mode):
        call(["sudo", "mount", volume_path, target_dir])
    else:
        click.echo("Not a block device: " + disk_path)

@anpr.command('umount', short_help="Unmount the anpr database files")
@click.argument('mssql-file-format', required = True, type = click.Choice(['bak', 'mdf']))
def umount(mssql_file_format):
    """
    Unmount the openstack volume containing the bak or mdf files.

    Pick the data type held by the disk you wish to unmount {'bak', 'mdf'} and  the folder 'bakfile' or 'dbfiles' will be unmounted accordingly.

    Sudo permissions are required. If user does not have passwordless sudo it will prompt for a password.
    """
    if mssql_file_format == 'mdf':
        target_dir = dbfiles_path
    else:
        target_dir = bakfile_path
    if os.path.ismount(target_dir):
        call(["sudo", "umount", target_dir])
    else:
        click.echo("Target dir is not mounted: " + target_dir)

@anpr.command('ls-mounts', short_help="Show mount status")
def lsmounts():
    """
    Show the status of expected anpr data mount locations.

    Data volumes if properly mounted, using this script, are expected to be mounted to a specific folder. This command allows the user to list and check the status of expected mount points.
    """
    click.echo("Expected Mount Location --- Status --- Volume's Purpose")

    if os.path.ismount(bakfile_path):
        click.echo(bakfile_path + " --- MOUNTED --- " + "Mssql Database Backup File (.bak)")
    else:
        click.echo(bakfile_path + " --- NOT MOUNTED --- " + "Mssql Database Backup File (.bak)")

    if os.path.ismount(dbfiles_path):
        click.echo(dbfiles_path + " --- MOUNTED --- " + "Mssql Database Files (.mdf, .ldf)")
    else:
        click.echo(dbfiles_path + " --- NOT MOUNTED --- " + "Mssql Database Files (.mdf, .ldf)")

@anpr.command('pull-image', short_help="Pull the mssql-server docker image")
def pull():
    """
    Pull the mssql-server image from docker's registry.

    The microsoft sql-server runs inside a container created from the docker image microsoft/mssql-server-linux. Before running the anpr-server the image needs to be downloaded and available in the system.
    """
    client = docker.from_env()
    if not client.images.list(name = image_name):
        click.echo("Pulling image, this may take a while...")
        client.images.pull(image_name, tag = "latest")
        click.echo("Done")
    else:
        click.echo("Skipped: image exists")

@anpr.command('start', short_help="Start the anpr-mssql-server")
@click.option('--password', '-p',
             type = str,
             envvar = 'SQL_PASSWORD',
             required = True,
             help = "Database password for SA user. Read from environment variable 'SQL_PASSWORD'")
def run_container(password):
    """
    Run a new container named "anpr-mssql-server".

    The microsoft/mssql-server-linux docker image is an official image for Microsoft SQL Server on Linux for Docker Engine and is designed to be used in real production environments and support real workloads. Therefore, I think we can assume that the container can be run for long periods of time and won't be restarted frequently. As a result, we do not persist the master database, which records all the system-level information for a SQL Server system. Instead, the openstack volumes containing the dbfiles should be used to store the database fles.
    
    The server is configured similarly to what is documented at https://hub.docker.com/r/microsoft/mssql-server-linux/.

    The system administrator password must be provided via the environment variable 'SQL_SERVER_PASSWORD'.

    After initiating the container use commands 'restore' and 'attach' to restore and attach the anpr database respectively.
    """
    # Test if container exists
    container = getContainer()
    if container:
        click.echo("Server is already running")
        return
    # Build map of mountpoints for docker.run
    volumes = {bakfile_path : {'bind' : bakfile_container_path,
                               'mode' : 'ro'},
               dbfiles_path : {'bind' : dbfiles_container_path,
                               'mode' : 'rw'}}
    # Get the docker client
    client = docker.from_env()
    try:
        client.containers.run(image = image_name,
                              detach = True,
                              environment = { "ACCEPT_EULA" : "Y",
                                              "MSSQL_PID" : "Developer",
                                              "MSSQL_SA_PASSWORD" : password },
                              ports = {'1433/tcp' : ("127.0.0.1", 1433)},
                              cap_add = ["SYS_PTRACE"],
                              volumes = volumes,
                              restart_policy = {"Name" : "on-failure",
                                                "MaximumRetryCount" : 3},
                             name = container_name)
        click.echo("Started")
    except docker.errors.APIError as e:
        click.echo(e)
    except docker.errors.ContainerError as e2:
        click.echo(e2)


@click.option('--password', '-p',
             type = str,
             envvar = 'SQL_PASSWORD',
             required = True,
             help="Database password for SA user. Read from environment variable 'SQL_PASSWORD'")
@click.option('--dbname', type = str, default = 'CortexDBWarehouse', help="Name of database to restore")
@click.option('--name-map', type = str, help="Dictionary with the components of the MOVE clause that make up the restore database sql query. Format should be \"{componentName : componentFilename}\"")
@click.option('--verbose', '-v', is_flag=True)
@click.option('--bak-filename', type = str, default = 'CortexDBWarehouse_20170705.bak', help="Name of database backup file (just name, not path to)")
@anpr.command('restore', short_help="Restore the database")
def restore(password, dbname, name_map, verbose, bak_filename):
    container = getContainer()
    if not container:
        click.echo("Server is not running")
        return
    # Try to convert input String to Dict (if available)
    if name_map is None:
        name_map = default_db_namemap
    else:
        name_map = ast.literal_eval(name_map)
    # Check if bak-filename exists
    if not os.path.isfile("".join([bakfile_path, "/", bak_filename])):
        click.echo("No such bak file: {}".format("".join([bakfile_path, "/", bak_filename])))
        sys.exit(1)
    # Check if files already exist in target dir
    for filename in name_map.values():
        if os.path.isfile("".join([dbfiles_path, "/", filename])):
            click.echo("Destination dbfile file already exists: {}".format("".join([dbfiles_path, "/", filename])))
            sys.exit(1)

    # Run Query through sqlcmd
    query = query_restoredb_builder(dbname, name_map, bak_filename)
    if verbose:
        click.echo("\n[QUERY]")
        click.echo(query)
        click.echo("[---]")
    response = container.exec_run(
                       cmd = ["/opt/mssql-tools/bin/sqlcmd",
                              "-U", "sa",
                              "-P", password,
                              "-S", "localhost",
                              "-Q", query],
                       detach = True)
    if response != "":
        click.echo(response)
    click.echo("Restoring the database in the background")
    click.echo("Run this script again with command restore-progress to query the progress of the operation.")

@click.option('--password', '-p',
             type = str,
             envvar = 'SQL_PASSWORD',
             required = True,
             help = "Database password for SA user. Read from environment variable 'SQL_PASSWORD'")
@click.option('--dbname', type = str, default = 'CortexDBWarehouse', help="Name of database to restore")
@click.option('--name-map', type = str, help="Dictionary with the components of the MOVE clause that make up the restore database sql query. Format should be \"{componentName : componentFilename}\"")
@click.option('--verbose', '-v', is_flag=True)
@anpr.command('attach', short_help="Attach the anpr database")
def attach(password, dbname, name_map, verbose):
    """
    Attach the anpr database (mdf, ldf files) to the running server.
    """
    container = getContainer()
    if not container:
        click.echo("Server is not running")
        return
    # Try to convert input String to Dict (if available)
    if name_map is None:
        name_map = default_db_namemap
    else:
        name_map = ast.literal_eval(name_map)
    # Check if files dont exist in target dir
    for filename in name_map.values():
        if not os.path.isfile("".join([dbfiles_path, "/", filename])):
            click.echo("Source dbfile does not exist: {}".format("".join([dbfiles_path, "/", filename])))
            sys.exit(1)

   # Run Query through sqlcmd
    query = query_attachdb_builder(dbname, name_map)
    if verbose:
        click.echo("\n[QUERY]")
        click.echo(query)
        click.echo("[---]")
    response = container.exec_run(
                       cmd = ["/opt/mssql-tools/bin/sqlcmd",
                              "-U", "sa",
                              "-P", password,
                              "-S", "localhost",
                              "-Q", query],
                       detach = False)
    if response != "":
        click.echo(response)
    click.echo("Ok")


@anpr.command('status', short_help="Status of the anpr-mssql-server")
def get_status():
    """
    Look for a container named "anpr-mssql-server" and return its status.
    """
    container = getContainer()
    if container:
        click.echo(getContainer().status)
    else:
        click.echo("Stopped")

@click.option('--force', '-f', is_flag=True)
@anpr.command('stop', short_help="Stop the anpr-mssql-server")
def stop_container(force):
    """
    Looks for a container named "anpr-mssql-server" and stop it if is running. Soft timeout of 15 seconds.
    """
    container = getContainer()
    if not container:
        click.echo("Server is not running")
        return
    try:
        if force:
            timeout = 1
        else:
            timeout = 15
        container.stop(timeout = timeout)
        container.remove()
        click.echo("Stopped and removed")
    except docker.errors.APIError as e:
        click.echo(e)


@click.option('--password', '-p',
             type = str,
             envvar = 'SQL_PASSWORD',
             required = True,
             help="Database password for SA user. Read from environment variable 'SQL_PASSWORD'")
@anpr.command('restore-progress', short_help="Show restore database progress")
def show_db_restore_progress(password):
    """
    Show the progress of the restore database operation
    """
    container = getContainer()
    if not container:
        click.echo("Server is not running")
        return
    response =container.exec_run(
                       cmd = ["/opt/mssql-tools/bin/sqlcmd",
                              "-U", "sa",
                              "-P", password,
                              "-S", "localhost",
                              "-Q", query_restore_progress_builder()])
    click.echo(response)

@click.option('--password', '-p',
             type = str,
             envvar = 'SQL_PASSWORD',
             required = True,
             help="Database password for SA user. Read from environment variable 'SQL_PASSWORD'")
@anpr.command('connect', short_help="Connect to the anpr database")
def connect(password):
    """
    Connect to the database using sqlcmd
    """
    container = getContainer()
    if not container:
        click.echo("Server is not running")
        return
    
    cmd = [ "docker",
            "exec",
            "-it",
            container_name,
            "/opt/mssql-tools/bin/sqlcmd",
            "-U", "sa",
            "-P", password,
            "-S", "localhost"]

    call(cmd)


##############################################
##############################################
##############################################

if __name__ == "__main__":
    if os.getuid() == 0:
	sys.exit("Do not run this script as root. If you need permissions to list and mount block devices, add your user to the 'disk' group.")
    anpr()
