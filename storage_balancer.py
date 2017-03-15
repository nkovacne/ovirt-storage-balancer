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

from funcs import SD, BYTES2GB, log, get_template_disk_ids, sort_disks_by_size, wait4unlock, get_vm_disk_map, find_vm_by_disk

try:
    from config import URI
except ImportError:
    print "ERROR: URI not specified in configuration. This parameter is mandatory"
    exit(1)

try:
    from config import USERNAME
except ImportError:
    print "ERROR: USERNAME not specified in configuration. This parameter is mandatory"
    exit(1)

try:
    from config import PASSWORD
except ImportError:
    print "ERROR: PASSWORD not specified in configuration. This parameter is mandatory"
    exit(1)

try:
    from config import CAPATH
except ImportError:
    print "ERROR: CAPATH not specified in configuration. This parameter is mandatory"
    exit(1)

try:
    from config import THRESHOLD
except ImportError:
    print "ERROR: THRESHOLD not specified in configuration. This parameter is mandatory"
    exit(1)

try:
    from config import DATACENTER
except ImportError:
    DATACENTER = None

try:
    from config import NOBALANCE
except ImportError:
    NOBALANCE = None

try:
    from config import DEBUG
except ImportError:
    DEBUG = False

try:
    from config import ITERATIONSLEEP
except ImportError:
    ITERATIONSLEEP = 300

try:
    from config import POLICY
    if POLICY != 'd' and POLICY != 'u' and POLICY != 'du':
        POLICY = 'du'
except ImportError:
    POLICY = 'du'

conn = Connection(
  url=URI,
  username=USERNAME,
  password=PASSWORD,
  ca_file=CAPATH,
)

if not conn.test(raise_exception=False):
    print "ERROR: Incorrect credentials. Please check your USERNAME, PASSWORD and CAPATH parameters."
    exit(2)

sys_serv = conn.system_service()

# Returns a list of SDs discarding those defined in NOBALANCE
# and including those defined in DATACENTERS, if set.
def get_sd_data():
    global NOBALANCE, DATACENTER, sys_serv
  
    sds = []
    sd_serv = sys_serv.storage_domains_service()
  
    sd_search_query = 'name != ovirt-image-repository'
    for nobal in NOBALANCE:
        sd_search_query += ' and name != %s' % (nobal)
    
    if DATACENTER:
        sd_search_query += ' and datacenter = %s' % (DATACENTER)
  
    for sd in sd_serv.list(search=sd_search_query):
       newsd = SD()
       newsd.name = sd.name
       newsd.free = sd.available
       newsd.used = sd.used
       newsd.percent_usage = int((newsd.used / float(newsd.used + newsd.free)) * 100)
       newsd.sd_p = sd
  
       sds.append(newsd)
  
    return sds

# Returns a list of sorted Storage Domains by free space.
# Also filters some SDs based on dynamic circumstances.
def filter_and_sort_sds(sds, current_sd):
    global THRESHOLD

    filtered = []

    for sd in sds:
        if sd.name == current_sd.name:
            log('Discarding SD %s as it\'s the same as the origin' % (sd.name), True)
            continue
        if sd.percent_usage >= THRESHOLD:
            log('Discarding SD %s as it\'s overused (%d perc.)' % (sd.name, sd.percent_usage), True)
            continue
        else:
            log('Including SD %s as suitable destination' % (sd.name), True)
            filtered.append(sd)

    filtered.sort(key=lambda x: x.free, reverse=True)
    return filtered

# Returns a migration map, i.e a dictionary with storage domains as keys and
# lists of disks as values. Those will be the disks that will be moved to each
# storage domain.
def make_migration_map(sd, disks_sorted):
    global THRESHOLD, BYTES2GB
    
    migration_map = {}
    theoretic_occupation_origin = sd.used

    log(' ', True)
    log('Filtering and sorting SDs...', True)
    sorted_sds = filter_and_sort_sds(get_sd_data(), sd)
    for sds in sorted_sds:
        log("SORTED SD: %s: %dGB" % (sds.name, sds.free / BYTES2GB), True)

    endloop = False
    log(' ', True)
    log('Processing now all disks to rebalance SD %s' % (sd.name), True)
    for disk in disks_sorted:
        if endloop:
            break

        for dest_sd in sorted_sds:
            theoretic_occupation_destination = dest_sd.used
            if not dest_sd in migration_map:
                migration_map[dest_sd] = []

            log('Checking if disk %s fits in %s... (disk real size: %d GB)' % (disk.id, dest_sd.name, disk.actual_size / BYTES2GB), True)
            if int(((theoretic_occupation_destination + disk.actual_size) / (float) (dest_sd.used + dest_sd.free)) * 100) < THRESHOLD:
                log('Disk fits without overflowing the threshold (maximum: %d perc.)' % (THRESHOLD), True)
                theoretic_occupation_origin -= disk.actual_size
                theoretic_occupation_destination += disk.actual_size
                migration_map[dest_sd].append(disk)

                log('Checking if after migrating disk the origin DS is below occupation threshold...', True)
                if int(((theoretic_occupation_origin) / (float) (sd.used + sd.free)) * 100) < THRESHOLD:
                    # At this point there's no need to keep on balancing more disks
                    # We just exit and the migration map is finished.
                    log('The origin SD is below occupation threshold. Map completed successfully.', True)
                    endloop = True
                else:
                    log('Origin SD would still be beyond occupation threshold. Processing next disk.', True)

                break
            else:
                log('Disk would trespass occupation threshold (%d perc.), processing next storage domain.' % (THRESHOLD), True)

    return migration_map

# Filter disks based on circumstances like it belongs to a template,
# or disk state is not 'ok', etc. Result will be a list of migratable disks
def filter_disks(vmdiskmap, disks):
    global sys_serv, POLICY

    filtered = []
    template_disk_ids = get_template_disk_ids(sys_serv)

    for disk in disks:
        vm = find_vm_by_disk(sys_serv, vmdiskmap, disk)
        if vm is None:
            if disk.id in template_disk_ids:
                log('Disk %s belongs to template, discarding' % (disk.id), True)
                continue
            if disk.name == 'OVF_STORE':
                log('Disk %s is a OVF_STORE disk, discarding' % (disk.id), True)
                continue
            else:
                log('Disk %s with no associated VM, adding' % (disk.id), True)
                filtered.append(disk)
        else:
            if disk.status != types.DiskStatus.OK:
                log('Disk %s has a different state from ok (%s), discarding' % (disk.id, disk.status.value), True)
                continue
            if vm.status == types.VmStatus.UP and vm.stateless:
                log('Discarding disk %s as it belongs to a VM that is stateless and up (%s)' % (disk.id, vm.name), True)
                continue
            if vm.status == types.VmStatus.UP and POLICY == 'd':
                log('Discarding disk %s as it belongs to a VM that is up (%s) and the policy is \'%s\'' % (disk.id, vm.name, POLICY), True)
                continue
            if vm.status == types.VmStatus.DOWN and POLICY == 'u':
                log('Discarding disk %s as it belongs to a VM that is down (%s) and the policy is \'%s\'' % (disk.id, vm.name, POLICY), True)
                continue
            else:
                log('Disk %s seems migrable (VM: %s), adding' % (disk.id, vm.name), True)
                filtered.append(disk)
    return filtered

# Initiate the rebalance process of the given SD
def rebalance_sd(sd):
    global sys_serv, BYTES2GB

    log('Rebalancing storage domain %s ...' % (sd.name))

    vmdiskmap = get_vm_disk_map(sys_serv)
    vms = sys_serv.vms_service()
    disks = sys_serv.disks_service()

    vmnames = []

    log('Gathering disks from storage domain %s' % (sd.name), True)
    disks_unsorted = disks.list(search='Storage = %s' % (sd.name))
    if not disks_unsorted:
        log('WARN: Couldn\'t get any migrable disk from storage domain %s, rebalancing cannot be performed.' % (sd.name))
        return None

    log('Applying disk filter policies...', True)
    filtered_disks = filter_disks(vmdiskmap, disks_unsorted)
    disks_sorted = sort_disks_by_size(filtered_disks)

    log(' ', True)
    log('Creating migration map...', True)
    migration_map = make_migration_map(sd, disks_sorted)

    if not migration_map:
        log('WARN: No migration map. Cannot perform rebalancing.')
    else:
        log(' ', True)
        log('Migration map obtained:', True)
        for migr_sd, migr_disks in migration_map.items():
            log("%s -> %s" % (migr_sd.name, migr_disks), True)

        for migr_sd, migr_disks in migration_map.items():
            for disk in migr_disks:
                vm = find_vm_by_disk(sys_serv, vmdiskmap, disk)
                vmname = vm.name if vm else '<NoVM>'

                log('Moving disk %s (VM: %s) -> %s (%dGB)' % (disk.id, vmname, migr_sd.name, disk.actual_size / BYTES2GB))
                disks_serv = disks.disk_service(id=disk.id)
                disks_serv.move(storage_domain=migr_sd.sd_p)
                wait4unlock(sys_serv, disk.id)
        log('RESULT: Storage domain %s has been rebalanced.' % (sd.name))
    return True

# Lists each data store with their occupation and makes decisions
# whether they need to be rebalanced or not.
def analyze_datastores():
    global THRESHOLD

    bal_needed = False

    log("Analyzing occupation of storage domains...", True)
    for sd in get_sd_data():
        log("%s -> %d perc." % (sd.name, sd.percent_usage), True)
        if sd.percent_usage >= THRESHOLD:
            bal_needed = True

            log('Storage domain %s is overused: (%d perc.), limit is %d perc.' % (sd.name, sd.percent_usage, THRESHOLD))
            balance_result = rebalance_sd(sd)
            if balance_result is None:
                log('WARN: Rebalancing result: Rebalancing couldn\'t be perfomed.')

    if not bal_needed:
        log('RESULT: No rebalancing needed, all storage domains are below occupation threshold.', True)
    log('- - - - - - - - - - - - - - - - -', True)

# Lists current storage domain occupation
def show_occupation():
    global THRESHOLD

    log("Analyzing occupation of storage domains...")
    for sd in get_sd_data():
        log("%s -> %d perc." % (sd.name, sd.percent_usage))
        if sd.percent_usage >= THRESHOLD:
            log('Storage domain %s is overused: (%d perc.), limit is %d perc.' % (sd.name, sd.percent_usage, THRESHOLD))

# Ctrl-C signal
def signal_handler(signal, frame):
    global conn
    conn.close()
    exit(0)

signal.signal(signal.SIGINT, signal_handler)

parser = argparse.ArgumentParser()
parser.add_argument('--one-run', action='store_true', help='Just executes the balancer once (one step)')
parser.add_argument('--daemon', action='store_true', help='Executes balancer as daemon. By default.')
parser.add_argument('--show-occupation', action='store_true', help='Only shows current storage domain occupation, then exits..')

args = parser.parse_args()

if args.one_run:
    analyze_datastores()
elif args.show_occupation:
    show_occupation()
else:
    while True:
        analyze_datastores()
        sleep(ITERATIONSLEEP)
