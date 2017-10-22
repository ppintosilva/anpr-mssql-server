# anpr-mssql

## Setup

### Attach an openstack volume to an instance

```

```

### Running the makefile

After the volume has been attached to the instance, it still needs to be mounted as a filesystem in order to be usable. But first, you need to find 

```
# fdisk -l
...
Disk /dev/vdb: 500 GiB, 536870912000 bytes, 1048576000 sectors
...

$ ls -l /dev/disk/by-id/
...
lrwxrwxrwx 1 root root  9 Sep 13 16:22 virtio-0604d3e4-c332-43ec-9 -> ../../vdb
...
```

This only needs to be done once:
```
# mkfs.ext4 /dev/disk/by-id/virtio-0604d3e4-c332-43ec-9 
```

Then you should be able to mount the the volume on a folder of your choice.
The makefile does this for you. It 
```
export ANPR_VOLUME_DISK_ID="virtio-0604d3e4-c332-43ec-9"

```
