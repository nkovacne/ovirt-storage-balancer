# oVirt storage balancer

This script takes all configured Storage Domains of oVirt and balances their disks under a defined threshold of occupation. You may exclude certain storage domains, focus it on a concrete data center, adjust the desired threshold and even apply a migration policy (only disks from machines that are up/down at that time, whatever VM's disks...).

This project uses ovirt-engine-sdk-python version 4.x.

**Note: This is an unofficial oVirt-related project**

### Installation

```
virtualenv venv
. venv/bin/activate
pip install -r requirements.txt
```

### Configuration
Copy the `config.py.example` file as `config.py` and adjust parameters to your needs. An explaination can be found inside the file comments.

### Script invocation

```
# python storage_balancer.py -h
usage: storage_balancer.py [-h] [--one-run] [--daemon] [--show-occupation]

optional arguments:
  -h, --help         show this help message and exit
  --one-run          Just executes the balancer once (one step)
  --daemon           Executes balancer as daemon. By default.
  --show-occupation  Only shows current storage domain occupation, then
                     exits..
```

* If run without parameters, daemon mode will be invoked.
* `--one-run` and `--show-occupation` are incompatible with `--daemon` mode, and they have precedence over this latter.

### Version

This is version 1.2.
