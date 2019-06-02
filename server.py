# anpr-mssql-server.py
#-------------------------------------------------------------------------------
# Quickly configure and deploy your ANPR Microsoft SQL-Server database
# as a docker container on Linux (Debian)
#-------------------------------------------------------------------------------
# Author: Pedro Pinto da Silva
# Version: v2.0.0
# License: MIT
#-------------------------------------------------------------------------------
# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------

import os
import sys
import time
import toml
import click
import docker
import subprocess

#-------------------------------------------------------------------------------
#
#
#   Global Variables / Config
#
#
#-------------------------------------------------------------------------------

config_file = "./config.toml"
config = toml.load(config_file)

volume_map = {
    'mdf': {
        'source' : config["anpr"]["dirs"]["mdf"],
        'target' : config["container"]["dirs"]['mdf'],
        'desc' : 'Mssql Database Files (.mdf, .ldf)'
     },
    'bak': {
        'source' : config["anpr"]["dirs"]["bak"],
        'target' : config["container"]["dirs"]["bak"],
        'desc' : 'Mssql Database Backup File (.bak)'
    },
    'tempdb': {
        'source' : config["anpr"]["dirs"]["tempdb"],
        'target' : config["container"]["dirs"]["tempdb"],
        'desc' : 'Mssql Runtime Files (tempdb, master)'
    }
}

volumes = {
    value['source'] : {
        'bind' : value['target'],
        'mode' : 'rw'
    }
    for key, value in volume_map.items()
}

#-------------------------------------------------------------------------------
#
#
#   Queries
#
#
#-------------------------------------------------------------------------------

def query_restoredb_builder(dbname, db_namemap, bakfile_name):
    move_lines = []

    for dbComponent, componentFilename in db_namemap.items():
        move_lines.append("MOVE ''{}'' TO ''{}''".format(
            dbComponent,
            "{}/{}".format(
                volume_map['mdf']['target'],
                componentFilename)
                )
        )

        sql_function = " ".join([
            "RESTORE DATABASE {}".format(dbname),
            "FROM DISK = ''{}''".format(
                "{}/{}".format(
                    volume_map['bak']['target'],
                    bakfile_name)
            ),
            "WITH {}, STATS = 10".format(", ".join(move_lines)),
        ])

    return "\n".join([
        "USE master",
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
        filename_lines += "@filename{} = \"{}\"{} ".format(
            i+1,
            "".join([
                volume_map['mdf']['target'], "/",
                filenames[i]]
                ),
            separator
        )

    return " ".join([
        "EXEC sp_attach_db @dbname ='{}',".format(dbname),
        filename_lines])

def query_restore_progress_builder():
    return ("SET NOCOUNT ON;SELECT start_time,cast(percent_complete as int) "
            "as progress,dateadd(second,estimated_completion_time/1000, "
            "getdate()) as estimated_completion_time, "
            "cast(estimated_completion_time/1000/60 as int) as minutes_left "
            "FROM sys.dm_exec_requests r WHERE r.command='RESTORE DATABASE'")

def query_configure_ram(ram = 2048):
    return "\n".join([
        "exec sp_configure 'show advanced options', 1",
        "GO",
        "RECONFIGURE",
        "GO",
        "exec sp_configure 'max server memory', {}".format(ram),
        "GO",
        "RECONFIGURE",
        "GO"
    ])

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
        return client.containers.get(config["container"]["name"])
    except docker.errors.NotFound as e:
        # click.echo(e)
        return None
    except docker.errors.APIError as e2:
        #    click.echo(e2)
        return None

#-------------------------------------------------------------------------------
#
#
#   Command Line Interface
#
#
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
@click.group(
    help="This is a wrapper application to ease the setup and management "
         "of the automatic number plate recognition (ANPR) microsoft "
         "sql-server database"
)
#-------------------------------------------------------------------------------
def anpr():
    pass

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
@anpr.command(
    'pull-image',
    short_help="Pull the mssql-server docker image"
)
#-------------------------------------------------------------------------------
def pull():
    """
    Pull the mssql-server image from docker's registry.

    The microsoft sql-server runs inside a container created from
    the docker image microsoft/mssql-server-linux. Before running the
    anpr-server the image needs to be downloaded and available in the system.
    """

    client = docker.from_env()
    image_name = config["container"]["image"]
    tag = config["container"]["tag"]

    if not client.images.list(name = image_name):
        click.echo("Pulling image {}:{}. This may take a while..."\
                   .format(image_name,tag))
        client.images.pull(image_name, tag = tag)
        click.echo("Done")
    else:
        click.echo("Skipped: image exists")

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------

@click.option('--password', '-p',
     type = str,
     envvar = 'SQL_PASSWORD',
     required = True,
     help = "Database password for SA user. "
            "Read from environment variable 'SQL_PASSWORD'")
@click.option(
    '--dry-run',
    is_flag=True,
    help = "Print query string without running the query."
)
@click.option('--ram',
      type = int,
      required = False,
      default = 2048,
      help = "Maximum ram used by mssql-server")
#-------------------------------------------------------------------------------
@anpr.command(
    'start',
    short_help="Start the anpr-mssql-server"
)
#-------------------------------------------------------------------------------
def run_container(password, ram, dry_run):
    """
    Run a new container named "anpr-mssql-server".

    The microsoft/mssql-server-linux docker image is an official image
    for Microsoft SQL Server on Linux for Docker Engine and is designed to
    be used in real production environments and support real workloads.
    Therefore, I think we can assume that the container can be run for long
    periods of time and won't be restarted frequently. As a result, we do not
    persist the master database, which records all the system-level information
    for a SQL Server system. Instead, the openstack volumes containing the
    dbfiles should be used to store the database fles.

    The server is configured similarly to what is documented at
    https://hub.docker.com/r/microsoft/mssql-server-linux/.

    The system administrator password must be provided via the environment
    variable 'SQL_SERVER_PASSWORD'.

    After initiating the container use commands 'restore' and 'attach'
    to restore and attach the anpr database respectively.
    """
    # Test if container exists
    container = getContainer()
    if container:
        click.echo("Server is already running")
        return

    # Get the docker client
    client = docker.from_env()
    try:
        params = dict(
            image = "{}:{}".format(
                        config["container"]["image"],
                        config["container"]["tag"]),
            detach = True,
            environment = {
                "ACCEPT_EULA"       : "Y",
                "MSSQL_PID"         : config["container"]["run"]["mssql_pid"],
                "MSSQL_SA_PASSWORD" : password
            },
            ports = {
                '1433/tcp' : ("127.0.0.1", 1433)
            },
            cap_add = ["SYS_PTRACE"],
            network_mode = config["container"]["run"]["network_mode"],
            volumes = volumes,
            name = config["container"]["name"]
        )
        if dry_run:
            click.echo(toml.dumps(params))
        else:
            click.echo("Gracefully starting the mssql-server..")
            container = client.containers.run(**params)

            click.echo("Started")
            # Let the server start gracefully before attempting any query
            time.sleep(config["container"]["run"]["graceful_timeout"])

        # Reconfigure max ram used by mssql server (unlimited by default),
        # otherwise large queries will hijack the entire system's RAM,
        # trigger memory swaps and make the system slow and useless
        cmd = [
            "/opt/mssql-tools/bin/sqlcmd",
            "-U", "sa",
            "-P", password,
            "-S", "localhost",
            "-Q", query_configure_ram(ram)]

        if dry_run:
            click.echo(" ".join(cmd))
        else:
            response = container.exec_run(cmd)
            #click.echo(response)
            click.echo("Reconfigured max ram = {}".format(ram))
    except docker.errors.APIError as e:
        click.echo(e)
    except docker.errors.ContainerError as e2:
        click.echo(e2)

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------

@click.option(
    '--password', '-p',
     type = str,
     envvar = 'SQL_PASSWORD',
     required = True,
     help = "Database password for 'SA' user "
            "read from environment variable 'SQL_PASSWORD'"
)
@click.option(
    '--dry-run',
    is_flag=True,
    help = "Print query string without running the query."
)
@click.argument(
    'bakfile',
    type = str,
    nargs = 1
    #help = "Name of the database backup file (only the name, not the path)"
)
#-------------------------------------------------------------------------------
@anpr.command(
    'restore',
    short_help = "Restore the database"
)
#-------------------------------------------------------------------------------
def restore(password, dry_run, bakfile):
    container = getContainer()
    if not container:
        click.echo("Server is not running")
        return
    # Try to convert input String to Dict (if available)
    name_map = config["anpr"]["move"]

    # Check if bak-filename exists
    if not os.path.isfile("".join([volume_map['bak']['source'], "/", bakfile])):
        click.echo("No such bak file: {}".format("".join([volume_map['bak']['source'], "/", bakfile])))
        sys.exit(1)

    # Check if files already exist in target dir
    for filename in name_map.values():
        if os.path.isfile("".join([volume_map['mdf']['source'], "/", filename])):
            click.echo("Destination dbfile file already exists: {}".format("".join([volume_map['mdf']['source'], "/", filename])))
            sys.exit(1)

    # Run Query through sqlcmd
    query = query_restoredb_builder(config["anpr"]["dbname"], name_map, bakfile)
    if dry_run:
        click.echo("\n[QUERY]")
        click.echo(query)
        click.echo("[---]")
        return
    else:
        response = container.exec_run(
           cmd = ["/opt/mssql-tools/bin/sqlcmd",
          "-U", "sa",
          "-P", password,
          "-S", "localhost",
          "-Q", query],
           detach = True)
        click.echo(response.output)
        click.echo("Restoring the database in the background")
        click.echo("Run this script again with command restore-progress to query the progress of the operation.")

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------

@click.option(
    '--password', '-p',
     type = str,
     envvar = 'SQL_PASSWORD',
     required = True,
     help = "Database password for SA user. Read from environment variable 'SQL_PASSWORD'"
)
@click.option(
    '--dry-run',
    is_flag=True,
    help = "Print query string without running the query."
)
#-------------------------------------------------------------------------------
@anpr.command(
    'attach',
    short_help="Attach the anpr database"
)
#-------------------------------------------------------------------------------
def attach(password, dry_run):
    """
    Attach the anpr database (mdf, ldf files) to the running server.
    """
    container = getContainer()
    if not container:
        click.echo("Server is not running")
        return
    # Try to convert input String to Dict (if available)
    name_map = config["anpr"]["move"]

    # Check if files dont exist in target dir
    for filename in name_map.values():
        if not os.path.isfile("".join([volume_map['mdf']['source'], "/", filename])):
            click.echo("Source dbfile does not exist: {}".format("".join([volume_map['mdf']['source'], "/", filename])))
            sys.exit(1)

   # Run Query through sqlcmd
    query = query_attachdb_builder(config["anpr"]["dbname"], name_map)
    if dry_run:
        click.echo("\n[QUERY]")
        click.echo(query)
        click.echo("[---]")
    else:
        response = container.exec_run(
            cmd = [
                "/opt/mssql-tools/bin/sqlcmd",
                "-U", "sa",
                "-P", password,
                "-S", "localhost",
                "-Q", query],
                detach = False)
        click.echo(response.output)

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
@anpr.command(
    'status',
    short_help="Status of the anpr-mssql-server"
)
#-------------------------------------------------------------------------------
def get_status():
    """
    Look for a container named "anpr-mssql-server" and return its status.
    """
    container = getContainer()
    if container:
        click.echo(getContainer().status)
    else:
        click.echo("Stopped")

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------

@click.option(
    '--force', '-f',
    is_flag=True)
@anpr.command(
    'stop',
    short_help="Stop the anpr-mssql-server"
)
#-------------------------------------------------------------------------------
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

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------

@click.option(
    '--password', '-p',
     type = str,
     envvar = 'SQL_PASSWORD',
     required = True,
     help = "Database password for 'SA' user. Read from environment variable 'SQL_PASSWORD'")
#-------------------------------------------------------------------------------
@anpr.command(
    'restore-progress',
    short_help = "Show the progress of the operation restore"
)
#-------------------------------------------------------------------------------
def show_db_restore_progress(password):
    """
    Show the progress of the restore database operation
    """
    container = getContainer()
    if not container:
        click.echo("Server is not running")
        return
    while(True):
        response = container.exec_run(
            cmd = [
                "/opt/mssql-tools/bin/sqlcmd",
                "-U", "sa",
                "-P", password,
                "-S", "localhost",
                "-Q", query_restore_progress_builder()]
        )
        click.echo(response.output)
        time.sleep(30)

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------

@click.option('--password', '-p',
     type = str,
     envvar = 'SQL_PASSWORD',
     required = True,
     help="Database password for SA user. Read from environment variable 'SQL_PASSWORD'"
)
#-------------------------------------------------------------------------------
@anpr.command(
    'connect',
    short_help="Connect to the anpr database"
)
#-------------------------------------------------------------------------------
def connect(password):
    """
    Connect to the database using sqlcmd
    """
    container = getContainer()
    if not container:
        click.echo("Server is not running")
        return

    cmd = [
        "docker",
        "exec",
        "-it",
        config["container"]["name"],
        "/opt/mssql-tools/bin/sqlcmd",
        "-U", "sa",
        "-P", password,
        "-S", "localhost"]

    subprocess.call(cmd)


##############################################
##############################################
##############################################

if __name__ == "__main__":
    if os.getuid() == 0:
        sys.exit("Do not run this script as root.")
    else:
        anpr()
