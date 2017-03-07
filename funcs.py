#!/usr/bin/env python
# -*- coding: utf-8 -*-

#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#
# See licensing in the LICENSE file #
#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#@#

from ovirtsdk4 import types, Error, Connection

import signal
import argparse
from sys import path, exit
from time import sleep, gmtime, strftime

from config import DEBUG

##########################################
################# STRUCTS ################
##########################################

class SD:
  name = None
  free = 0
  used = 0
  percent_usage = 0
  sd_p = None

BYTES2GB = 1024**3

##########################################
############## END STRUCTS  ##############
##########################################

# Logs a line to stdout
def log(line, logdebug=False):
    global DEBUG

    if not logdebug:
        print "[%s] %s" % (strftime("%Y-%m-%d %H:%M:%S", gmtime()), line)
    if logdebug and DEBUG:
        print "[%s][DEBUG] %s" % (strftime("%Y-%m-%d %H:%M:%S", gmtime()), line)

# Returns a list of all template disk's IDs (will be marked as non-migratable)
def get_template_disk_ids(sys_serv):
    tpl_disk_ids = []
    tpl_serv = sys_serv.templates_service()
    for tpl in tpl_serv.list():
        ts_tpl_serv = tpl_serv.template_service(id=tpl.id)
        disk_tpl_serv = ts_tpl_serv.disk_attachments_service()
        for disk in disk_tpl_serv.list():
            tpl_disk_ids.append(disk.id)
    return tpl_disk_ids

# Returns a list of disks sorted by actual_size
def sort_disks_by_size(disks):
    disks.sort(key=lambda x: x.actual_size, reverse=True)
    return disks

# Waits until the disk with diskid returns to status "ok"
def wait4unlock(sys_serv, diskid):
    disks = sys_serv.disks_service()

    log('Waiting for disk %s being unlocked...' % (diskid), True)
    sleep(10)
    while True:
        diskobj = disks.list(search='id=%s' % (diskid))[0]
        if diskobj.status == types.DiskStatus.LOCKED:
            sleep(30)
        else:
            log('Disk %s unlocked (Status: %s)' % (diskid, diskobj.status.value), True)
            break

# Maps VMs and IDs of their disks (used to know which VMs are up and down)
# based on disk IDs.
def get_vm_disk_map(sys_serv):
    vmdiskmap = {}
    
    vm_serv = sys_serv.vms_service()
    for vm in vm_serv.list():
        vmdiskmap[vm] = []
        vms = vm_serv.vm_service(id=vm.id)
        disks = vms.disk_attachments_service()
        for disk in disks.list():
            vmdiskmap[vm].append(disk.id)

    return vmdiskmap

# Returns the VM associated to a disk
def find_vm_by_disk(sys_serv, vmdiskmap, disk):
    vm_serv = sys_serv.vms_service()
    for vm, disks in vmdiskmap.items():
        if disk.id in disks:
            return vm
    return None
