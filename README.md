# anpr-mssql-server
Tools for deploying the ANPR Microsoft SQL-Server database as a docker container on a ubuntu server

## Context
Automatic Number Plate Recognition (ANPR) data is used actively in law enforcement and in traffic management and control. The data originates from roadside cameras that automatically detect the number plates of passing vehicles. It is stored and maintained in a sql-server database. We've been kindly granted a copy of part of the database, for research purposes.

### Assumptions

Due to it's size (hundreds of GB), it's usually unfeasible to deploy the entire dataset on your personal computer. At the moment, I'm using the university-managed cloud, running Openstack, to store the anpr data files and run the `anpr-mssql-server`. Openstack uses block storage devices, called volumes, that can be attached to computing instances to enable persistent storage. Similar architectures are found in other cloud providers.

As such, the script simply assumes that the database files are available through a block device. It does not try to assume that you are using Openstack as a cloud provider nor attempts to do any pre-configuration (e.g. attach a network block device, create a filesystem). Therefore, depending on your setup, you might need to do some pre-configuration yourself in order to make the volume available as a block device in your computing instance. Below is an explanation of how to do it for Openstack.

Sql-server database files can exist as backup files (.bak) or a series of primary and transaction database files (.mdf, .ldf). If the database files are in format .bak (usually just a single file), then this is a backup of the database and it needs to be restored for the database to be usable. Additionally, the restoration process re-creates the .mdf and .ldf files from the .bak file. Therefore, to complete this process you may find that you need nearly the double of the space necessary to store the database. As such, we assume that these files (the backup file and primary files) live in different volumes and are hence available on different block devices. We understand that is not very flexible but enforces best practices when it comes to separating files based on their functionality. Furthermore, after restoring the database, the bakfile won't be needed by sql-server and you can simply detach that volume from your instance.

### Pre-configuration in Openstack

Once you create a volume in Openstack with the necessary size, you can attach it to the instance using the dashboard on the command line interface. If you're using the volume for the first time you will have to create a new file system. For ubuntu's use case, you can create a ext4 filesystem:

```# mkfs -t ext4 'path_to_dev_file'```

You will need to do this for each new volume that you're attaching.

## Installation

A makefile is used to take care of the python environment and dependencies required by the script. This makefile was written specifically to work on ubuntu server. Interoperability with other operating systems is not guaranteed. Nevertheless, the actions performed by the makefile are quite straightforward. It starts by installing python2.7, pip and virtualenv for the current user, if it isn't the case already. Then a virtual environment is created and the dependencies are installed using pip. Running `make install` performs these actions and verifies that `server.py` runs its usage successfully.

**Note:** The makefile won't install docker for you.

## Usage

Before starting to use the server script, make sure the virtual environment is active.

```source ENV/bin/activate```

You can then run the script as `python server.py`. The following operations are allowed:

```
ls-disks    List available block devices
ls-uuids    List the uuid of available block devices
ls-mounts   Show the status of expected mountpoints
mount       Mount the anpr data volume containing the anpr database files
pull-image  Pull the mssql-server docker image
start       Start eh anpr-mssql-server
status      Show the status of the anpr-mssql-server
stop        Stop the anpr-mssql-server
umount      Unmount the anpr data volume
```

### Preparing the server

### Starting the server

## Querying the database

This script pertains to the setup of the server itself. A separate application has been built to provide a client interface for querying the database. The client side python script is available [here](https://github.com/NCL-CloudComputing/anpr-mssql-client).
