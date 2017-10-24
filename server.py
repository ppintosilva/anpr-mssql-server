#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
server.py is an interactive script for managing
"""

from subprocess import call
import os
import stat
import click
import docker

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

###############################################
#
#
#   Helpers
#
#
###############################################

def listSymbolicLinks(folder):
    ids = os.listdir(folder)
    for ident in ids:
        click.echo(ident + " ---> " + os.path.realpath(folder + ident))

def getContainer():
    client = docker.from_env()
    try:
        return client.containers.get(container_name)
    except docker.errors.NotFound as e:
        click.echo(e)
    except docker.errors.APIError as e2:
        click.echo(e2)
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

@anpr.command(name='ls-disks', help="List available block devices")
def lsdisks():
    """
    List available block devices.

    This operation is meant to help the user determining the block device which the openstack volume has been attached.

    Requires sudo permissions.
    """
    call(["sudo", "lsblk", "-o", "NAME,FSTYPE,SIZE,MOUNTPOINT,LABEL"])

@anpr.command(name='ls-uuids', help="List the uuid of available block devices")
def lsuuids():
    """
    List the uuid of available block devices.

    This operation is meant to help the user determining the uuid of the block device which the openstack volume has been attached.
    """
    listSymbolicLinks('/dev/disk/by-uuid/')

@anpr.command('mount', help="Mount the anpr database files")
@click.argument('disk-uuid', required = True, type = click.UUID)
@click.argument('mssql-file-format', required = True, type = click.Choice(['bak', 'mdf']))
def mount(disk_uuid, mssql_file_format):
    """
    Mount the openstack volume containing the bak or mdf files.

    This operation takes as input the uuid of the block device corresponding to the openstack volume, which can be determined through the use of 'ls-disks' and 'ls-uuids' operations. The disk will be mounted on subdirectories 'bakfile' or 'dbfiles' depending on the format of the anpr data held by the openstack volume. If the anpr data consists of a backup restore file then it will be mounted in 'bakfile', otherwise if it consists of master and log database files, it will be mounted in 'dbfiles'. This behavior must specified in second parameter by passing one of the following values {'bak', 'mdf'}, respectively.

    Requires sudo permissions.
    """
    disk_path = "/dev/disk/by-uuid/" + str(disk_uuid)
    if mssql_file_format == 'mdf':
        target_dir = dbfiles_path
    else:
        target_dir = bakfile_path
    if stat.S_ISBLK(os.stat(disk_path).st_mode):
        call(["sudo", "mount", disk_path, target_dir])
    else:
        click.echo("No block device file with given uuid exists at: " + disk_path)

@anpr.command('umount', help="Unmount the anpr database files")
@click.argument('mssql-file-format', required = True, type = click.Choice(['bak', 'mdf']))
def umount(mssql_file_format):
    """
    Unmount the openstack volume containing the bak or mdf files.

    Pick the data type held by the disk you wish to unmount {'bak', 'mdf'} and  the folder 'bakfile' or 'dbfiles' will be unmounted accordingly.

    Requires sudo permissions.
    """
    if mssql_file_format == 'mdf':
        target_dir = dbfiles_path
    else:
        target_dir = bakfile_path
    if os.path.ismount(target_dir):
        call(["sudo", "umount", target_dir])
    else:
        click.echo("Target dir is not mounted: " + target_dir)

@anpr.command('ls-mounts', help="Show mount status")
def lsmounts():
    """
    Show the status of expected anpr data mount locations.
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

@anpr.command('pull-image', help="Pull the mssql-server docker image")
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

@anpr.command('start', help="Start the anpr sql-server")
@click.option('--password', '-p',
             type = str,
             envvar = 'SQL_SERVER_PASSWORD',
             required = True,
             help = "")
@click.argument('mode',
                required = True,
                type = click.Choice(['restore', 'attach']),
                default = 'attach')
def run_container(mode, password):
    """
    Run a new container named "anpr-mssql-server".

    The microsoft/mssql-server-linux docker image is an official image for Microsoft SQL Server on Linux for Docker Engine and is designed to be used in real production environments and support real workloads. Therefore, I think we can assume that the container can be run for long periods of time and won't be restarted frequently. As a result, we do not persist the master database, which records all the system-level information for a SQL Server system. Instead, the openstack volumes containing the dbfiles should be used to store the database fles. Then, on starting a new container we either re-create the anpr database by attaching the existing database files that should be mounted in 'dbfiles' (mdf, ldf), or by restoring the backup file that should be mounted in 'bakfile'. This behavior is specified by the parameter 'mode' and should be set to 'restore' or 'attach' depending on the format of the anpr data resources available: if bakfile then restore, else if mdf,ldf files then attach.

    The server is configured similarly to what is documented at https://hub.docker.com/r/microsoft/mssql-server-linux/.

    The system administrator password must be provided via the environment variable 'SQL_SERVER_PASSWORD'.
    """
    container = getContainer()
    if container:
        click.echo("Server is already running")
        return
    if mode == "attach":
        # If not mounted - exit
        volumes = {dbfiles_path : {'bind' : dbfiles_container_path,
                                   'mode' : 'ro'}}
    else:
        # If not mounted - exit
        volumes = {bakfile_path : {'bind' : bakfile_container_path,
                                    'mode' : 'ro'},
                   dbfiles_path : {'bind' : dbfiles_container_path,
                                   'mode' : 'rw'}}
    client = docker.from_env()
    # Verify that a running container does not exist already - docker does
    # this for us (no to containers with the same name are allowed)
    try:
        client.containers.run(image = image_name,
                              detach = True,
                              environment = { "ACCEPT_EULA" : "Y",
                                              "MSSQL_PID" : "Developer",
                                              "MSSQL_SA_PASSWORD" : password },
                              ports = {'1401/tcp' : ("127.0.0.1", 1433)},
                              cap_add = ["SYS_PTRACE"],
                              volumes = volumes,
                              restart_policy = {"Name" : "on-failure",
                                                "MaximumRetryCount" : 3},
                              name = container_name)
        click.echo("Started")
        if mode == "attach":
            # Run-Query Attach Database
            click.echo("Attaching the anpr database...")
        else:
            # Run-Query Restore Database
            click.echo("Restoring the anpr database...")

    except docker.errors.APIError as e:
        click.echo(e)
    except docker.errors.ContainerError as e2:
        click.echo(e2)

@anpr.command('status', help="Show the status of the anpr sql-server")
def get_status():
    """
    Look for a container named "anpr-mssql-server" and return its status.
    """
    container = getContainer()
    if container:
        click.echo(getContainer().status)

@anpr.command('stop', help="Stop the anpr sql-server")
def stop_container():
    """
    Look for a container named "anpr-mssql-server" and stop it if it's running. Soft timeout of 15 seconds.
    """
    container = getContainer()
    if not container:
        click.echo("Server is not running")
        return
    try:
        container.stop(timeout = 15)
        container.remove()
        click.echo("Stopped and removed")
    except docker.errors.APIError as e:
        click.echo(e)

##############################################
##############################################
##############################################

if __name__ == "__main__":
    anpr()
