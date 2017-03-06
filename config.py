# URI of the ovirt engine (should be something like: https://fqdn/ovirt-engine/api)
# This parameter is mandatory.
URI = 'https://your-ovirt/ovirt-engine/api'

# Username of the user which will move the disks. Make sure this account have the
# proper permissions to do so.
# This parameter is mandatory.
USERNAME = 'admin@internal'

# Password of the user
# This parameter is mandatory.
PASSWORD = '...'

# Path of the CA used by oVirt (needed for connecting in sdk4)
# This parameter is mandatory.
CAPATH = '/etc/pki/tls/certs/ca-bundle.crt'

# Percent of occupation beyond a storage domain will be balanced.
# This parameter is mandatory.
THRESHOLD = 85

# If set, only storage domains of these data centers will be balanced.
# Must be a string.
# This parameter is optional.
DATACENTER = ''

# If set, these storage domains won't be balanced, neither as origin or destination.
# Must be a Python list of storage domains' names.
# This parameter is optional.
NOBALANCE = []

# If set to True, a lot of information will be shown of the balancing process
DEBUG = False

# Time in seconds between different iterations of balancing
# Default: 300 seconds
ITERATIONSLEEP = 300

# Policy to use when balancing. 'du' per default.
# 'd' = Only machines that are down at the time of balancing will be taken into account in the balancing process 
# 'u' = Only machines that are up at the time of balancing will be taken into account in the balancing process 
# 'du' = Machines that are either up or down at the time of balancing will be taken into account in the balancing process (default)
POLICY = 'du'
