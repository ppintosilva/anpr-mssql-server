# anpr-mssql-server
Tools for deploying the ANPR Microsoft SQL-Server database as a docker container on a ubuntu server

## TL;DR

### Requirements

- An ubuntu cloud instance (or similar)
- A block storage volume containing the mssql database files (single .bak file or collection of .mdf/.ldf files)
- The volume is attached to the instance and available as a block storage device
- A filesystem has been created for the block device ```mkfs -t ext4 [block_device]```
- ```python-pip``` and ```docker``` are installed
- User is part of the ```docker``` group

### Run

- Clone the repo using a deploy key
- ```$ make install```
- ```$ source ENV/bin/activate```
- ```$ python server.py pull-image```
- ```$ python server.py ls-volumes``` -> if unsure about which block device corresponds to which data volume
- ```# python server.py mount [block_device_with_bak_file] bak```
- ```# python server.py mount [block_device_with_mdf_files] mdf```
- Set environment variable 'SQL_PASSWORD' (requires use of lowercase, uppercase and punctuation/digits - minimum of 10 characters)
- ```$ python server.py start```
- ```$ python server.py restore``` or ```python server.py attach```
- Expose port 1433 if querying the database from a different host

---

## Context
Automatic Number Plate Recognition (ANPR) data is used actively in law enforcement and in traffic management and control. The data originates from roadside cameras that automatically detect the number plates of passing vehicles. It is stored and maintained in a sql-server database. We've been kindly granted a copy of part of the database for research purposes.

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

Before using the server script, make sure that the virtual environment is active.

```source ENV/bin/activate```

You can then run the script using `python server.py [options] [command] [arguments]`. The following commands are allowed:

```
attach            Attach the anpr database
connect           Connect to the anpr database
ls-mounts         Show mount status
ls-volumes        List block devices
mount             Mount the anpr database files
restore           Restore the database
pull-image        Pull the mssql-server docker image
restore           Restore the anpr database
restore-progress  Show restore database progress
start             Start the anpr-mssql-server
status            Status of the anpr-mssql-server
stop              Stop the anpr-mssql-server
umount            Unmount the anpr database files
```

### Preparing the server

To help you determine the block device which holds the anpr database files, you can run the ```ls-volumes``` command:
```
python server.py ls-volumes

NAME                       FSTYPE   SIZE MOUNTPOINT
sr0                        iso9660  428K
vda                                   8G
└─vda1                     ext4       8G /
vdb                        ext4     500G
vdc                        ext4     400G
```

After that, you should mount the storage volumes using the ```mount``` command (requires sudo). If attaching the database, only the second command needs to be run, otherwise both are required (because the database is restored onto the database files in the other volume).
```
python server.py mount block_device_path bak

python server.py mount block_device_path mdf
```

You can check the status of your mount points by running:
```
python server.py ls-mounts

Expected Mount Location --- Status --- Volume's Purpose
/home/jsnow/anpr-mssql-server/bakfile --- MOUNTED --- Mssql Database Backup File (.bak)
/home/jsnow/anpr-mssql-server/dbfiles --- MOUNTED --- Mssql Database Files (.mdf, .ldf)
```

Before starting the server you will need to pull the docker image from the registry:
```
python server.py pull-image

(...)
```

### Starting and managing the server

Starting, querying the status of the server and stopping it can be made using commands ```start```, ```status``` and ```stop```, respectively. To start the server a password is required. This value is read by default from environment variable ```SQL_PASSWORD``` and should be the preferred way of passing this parameter. To be accepted by the SQL server database it most conform to the following format: use of lowercase, uppercase and punctuation/digits with a minimum of 10 characters. This value is also required for commands ```attach```, ```restore```, ```connect```, ```restore-progress```.

The ```attach``` command should be used once the 'mdf' and 'ldf' files are available. If only the 'bak' file is available, then the ```restore``` command should be used instead. As this process takes a long time, it is run in the background and the ```restore-progress``` command can be used to show its progress. The ```connect``` command can be used to connect to the database using the ```sqlcmd``` command.

The server status can be queried and stopped with the ```status``` and ```stop``` commands. The ```stop``` command accepts a ```--force/-f``` flag.


## Querying the database

This script pertains to the setup of the server itself. A separate application has been built to provide a client interface for querying the database. The client side python script is available [here](https://github.com/PedrosWits/anpr-mssql-client).
