# anpr-mssql-server

This python script automates the configuration and deployment of a ANPR database via a [mssql-server](https://hub.docker.com/_/microsoft-mssql-server) docker container.

## Requirements

- Docker (and user added to `docker` group)
- Python 3 (`pipenv` recommended)
- The sql-srv database files in one of two formats:
  - A single `.bak` file
  - A collection of `.mdf`/`.ldf` files
- Additional storage for sql-server's `tempdb` database files (again, one of: local, external, network attached)

## Steps

- Copy `default_config.toml` to `config.toml` and modify it according to your setup (the `[anpr.dirs]` section is a must)
- `$ pipenv install` + `$ pipenv shell` (or alternative virtualenv setup)
- ```$ python server.py pull-image```
- `$ export SQL_PASSWORD=YOUR_password_123` (requires use of lowercase, uppercase and punctuation/digits - minimum of 10 characters)
- `$ python server.py start`
- One of (use --dry-run flag to debug/verify queries):
  - `$ python server.py restore` if input is `.bak`
  - `$ python server.py attach` if input is `.mdf`  
- Expose port 1433 if querying the database from a different host

### Additional instructions for input via a block device on Linux Debian

If the database files are available via a block device (e.g.), then some pre-configuration might be necessary:

- (`$`) Find out the block device id/MOUNTPOINT:

  ```bash
  lsblk -o NAME,FSTYPE,SIZE,MOUNTPOINT
  ```

- (`#`) Format the filesystem on the block device:

  ```bash
  mkfs -t ext4 YOUR_BLOCK_DEVICE
  ```

- (`#`) Mount the block device:

  ```bash
   mount YOUR_BLOCK_DEVICE LOCAL_FOLDER_NAME
   ```

- Repeat the above steps for each block device containing data (you may have one block device hold a different type of database files {'bak', 'mdf', 'tempdb'}, or one storing all types)

---

## Context
Automatic Number Plate Recognition (ANPR) data is used actively in law enforcement and in traffic management and control. The data originates from roadside cameras that automatically detect the number plates of passing vehicles. It is stored and maintained in a sql-server database. We've been kindly granted a copy of a subset of the database for research purposes.

Due to it's size (hundreds of GB), it's often unfeasible to deploy the entire dataset on your personal computer. Therefore, a . Depending on which resources you have available this can be simply an external hard drive, a second hard drive if you're running a desktop, or some kind of network-attached storage. You might also be using a cloud provider. Independently of which method you're using to store the raw data, I've tried to make the script as configurable as possible (as opposed to earlier versions of this script, which made too many assumptions). This means however that it's up to you to make whatever method of data storage you used accessible (read+write permissions) to the script.

Sql-server database files can exist as backup files (.bak) or a series of primary and transaction database files (.mdf, .ldf). If the database files are in format .bak (usually just a single file), then this is a backup of the database and it needs to be restored for the database to be usable. Additionally, the restoration process re-creates the .mdf and .ldf files from the .bak file. Therefore, to complete this process you may find that you need nearly the double of the space necessary to store the database. You also need additional space for sql-server's temporary database files, which will grow in size as you make more and more extensive queries. However, after restoring the database, the bakfile won't be needed by sql-server, so you may choose to back it up in different place (e.g. not optimised for availability).

## Querying the database

This script pertains to the setup of the server itself. A separate application has been built to provide a client interface for querying the database. The client side python script is available [here](https://github.com/ppintosilva/anpr-mssql-client).
