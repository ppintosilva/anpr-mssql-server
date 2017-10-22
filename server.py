#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

This is a awesome python script!

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

@click.group()
def anpr():
    pass

@anpr.command(name='ls-disks')
def lsdisks():
    call(["sudo", "fdisk", "-l"])

@anpr.command(name='ls-uuids')
def lsuuids():
    listSymbolicLinks('/dev/disk/by-uuid/')

@anpr.command(name='mkfs')
@click.argument('disk-uuid', required = True, type = click.UUID)
def mkfs(disk_uuid):
    pass

@anpr.command('mount')
@click.argument('disk-uuid', required = True, type = click.UUID)
@click.argument('mssql-file-format', required = True, type = click.Choice(['bak', 'mdf']))
def mount(disk_uuid, mssql_file_format):
    disk_path = "/dev/disk/by-uuid/" + str(disk_uuid)
    if mssql_file_format == 'mdf':
        target_dir = dbfiles_path
    else:
        target_dir = bakfile_path
    if stat.S_ISBLK(os.stat(disk_path).st_mode):
        call(["sudo", "mount", disk_path, target_dir])
    else:
        click.echo("No block device file with given uuid exists at: " + disk_path)

@anpr.command('umount')
@click.argument('mssql-file-format', required = True, type = click.Choice(['bak', 'mdf']))
def umount(mssql_file_format):
    if mssql_file_format == 'mdf':
        target_dir = dbfiles_path
    else:
        target_dir = bakfile_path
    if os.path.ismount(target_dir):
        call(["sudo", "umount", target_dir])
    else:
        click.echo("Target dir is not mounted: " + target_dir)

@anpr.command('ls-mounts')
def lsmounts():
    click.echo("Expected Mount Location --- Status --- Volume's Purpose")

    if os.path.ismount(bakfile_path):
        click.echo(bakfile_path + " --- MOUNTED --- " + "Mssql Database Backup File (.bak)")
    else:
        click.echo(bakfile_path + " --- NOT MOUNTED --- " + "Mssql Database Backup File (.bak)")

    if os.path.ismount(dbfiles_path):
        click.echo(dbfiles_path + " --- MOUNTED --- " + "Mssql Database Files (.mdf, .ldf)")
    else:
        click.echo(dbfiles_path + " --- NOT MOUNTED --- " + "Mssql Database Files (.mdf, .ldf)")

@anpr.command('pull-image')
def pull():
    client = docker.from_env()
    if not client.images.list(name = image_name):
        click.echo("Pulling image, this may take a while...")
        client.images.pull(image_name, tag = "latest")
        click.echo("Done")
    else:
        click.echo("Skipped: image exists")

@anpr.command('start')
@click.option('--password', '-p',
             type = str,
             envvar = 'SQL_SERVER_PASSWORD',
             required = True)
@click.argument('mssql-file-format',
                required = True,
                type = click.Choice(['bak', 'mdf']),
                default = 'mdf')
def run_container(mssql_file_format, password):
    if mssql_file_format == "mdf":
        volumes = {dbfiles_path : {'bind' : dbfiles_container_path,
                                   'mode' : 'ro'}}
    else:
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
        # Run-Query Attach Database

        # Run-Query Restore Database

    except docker.errors.APIError as e:
        click.echo(e)
    except docker.errors.ContainerError as e2:
        click.echo(e2)

@anpr.command('status')
def get_status():
    container = getContainer()
    if container:
        click.echo(getContainer().status)

@anpr.command('stop')
def stop_container():
    container = getContainer()
    if not container:
        click.echo("Server is not running")
        return
    try:
        container.stop(timeout = 5)
        container.remove()
        click.echo("Stopped and removed")
    except docker.errors.APIError as e:
        click.echo(e)

##############################################
##############################################
##############################################

if __name__ == "__main__":
    anpr()
