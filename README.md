# cloud_validator

A Validator for the Cloud that runs in currently 3 different ways'
1. Validator Light, for quickly building a couple of VMs
2. Validator Custom, for running custom builds easily defined in yaml files (see below)
3. Validator Heavy, which can only be run when a region is empty, and builds as many VMs as possible.

# Validator Custom

Validator Custom allows custom project setups to be defined in yaml files and then be built with Validator.

## `project`
- `name` - Name of the project. Should be unique. (required)

## `subnets`
- `name` - Subnet name. Should be unique within a project. (required)
- `gateway` - The IP address of the gateway. (required)
- `mask` - The mask for the subnet (required)

## `vpn`
- `local_subnet` - local(cloud cix/alpha) private ntw from the project subnets. (required)
- `customer_subnets` - list of remote(user end) private ntw address(ipv4). (required)
- `ike_authentication` - a must field from static list [md5, sha1, sha-256, sha-384]
- `ike_encryption` - a must field from static list [aes-128-cbc, aes-192-cbc, aes-256-cbc, des-cbc, 3des-cbc]
- `ike_lifetime` - an interger value within range [180, 86400] (optional)
- `ike_dh_groups` - a must field from static list [group1, group2, group5, group19, group20, group24]
- `ike_pre_shared_key` - password(not more than 64 chars) for vpn connection establish. (required)
- `ike_version` - a must field from static list [v1-only, v2-only]
- `ike_mode` - a must field from static list [main, aggressive]
- `ike_public_ip` - floating IP address of the user
- `ipsec_authentication` - a must field from static list [hmac-md5-96, hmac-sha1-96, hmac-sha-256-96, hmac-sha-256-128]
- `ipsec_encryption` - a must field from static list [aes-256-cbc, aes-192-cbc, aes-256-cbc, des-cbc, 3des-cbc, aes-128-gcm, aes-192-gcm, aes-256-gcm]
- `ipsec_lifetime` - an interger value within range [180, 86400] (optional)
- `ipsec_pfs_groups` - a must field from static list [group1, group2, group5, group14, group19, group20, group24]
- `ipsec_establish_time` - a must field from static list [immediately, on-traffic]

## `vms`
- `random` - True if project should contain a certain number of randomly generated VMs. (required)
- `count` - The number of random VMs to be created. (required if random is True)
- `vm_list` - List of predefined VMs

### `vm_list`
- `name` - Name of the VM. (required)
- `dns` - The domain name servers to be used by the project. (required)
- `gateway_subnet` - RFC 1918 address range from subnets that the Gateway for the VM will be defined on. 
- `ip_addresses` The IP address for the VM. Must be within one of the defined subnets. Not required. If not included a random IP within one of the subnets will be assigned
  - `address`: IP Address of VM
  - `nat`: Boolean, only IPs from the gateway subnet can be NATed
- `cpu` - Number of CPU cores to be assigned. (required)
- `ram` - Amount of RAM in GB to be assigned. (required)
- `image_id` - ID of the operating system to be installed. (required)
  - 2 - Windows Server 2012
  - 3 - Windows Server 2016
  - 6 - Ubuntu Server 16.04
  - 10 - CentOS Linux 7
  - 12 - Ubuntu Server 18.04
  - 13 - Windows Server 2019
  - 14 - Manual
  - 15 - Red Hat Server 7.7
  - 16 - Centos Linux 8
  - 17 - Ubuntu Server 20.04
- `replicate` - Number of replicates of a VM there should be within a project. e.g 5 would produce five of the same VM. Not required.
- `storage_type_id` - ID of the storage type (required)
  - 1 is HDD
  - 2 is SSD
- `storage` - List of storage for the VM

#### `storage`
- `name` - Name of the storage. Should be unique within the VM. (required)
- `gb` - Size of the storage in GB. (required)
- `primary` - True if primary storage. Every VM must have one storage marked as primary. (required)


#### `firewall_rules`
- `allow` - True if the traffic matching the rule should be allowed through the firewall. (required)
- `destination` - A Subnet or IP Address representing the destination value for the rule. Use * to represent all. (required)
- `port` - The port to use when checking incoming traffic against this rule. Use * to represent all. (required)
- `protocol` - The protocol to use when checking incoming traffic against this rule. Options are [tcp, udp, any]. (required)
- `source` - A Subnet or IP Address representing the source value for the rule. Use * to represent all. (required)


## Example

```yaml
project:
  name: Test-Project

subnets:
  - name: Subnet-One
    gateway: 192.168.123.1
    mask: 24

vpn:
  local_subnet: 192.168.123.1/24
  customer_subnets: [172.16.32.0/24]
  ike_authentication: md5
  ike_encryption: aes-256-cbc
  ike_lifetime: 18000
  ike_dh_groups: group2
  ike_pre_shared_key: test
  ike_version: v1-only
  ike_mode: main
  ike_public_ip: 91.103.1.30
  ipsec_authentication: hmac-md5-96
  ipsec_encryption: aes-256-cbc
  ipsec_lifetime: 18000
  ipsec_pfs_groups: group2
  ipsec_establish_time: immediately

vms:
  random: true
  count: 2
  vm_list:
    - name: VM-ONE
      dns: 91.103.0.1,8.8.8.8
      cpu: 1
      ram: 1
      image_id: 10
      gateway_subnet: 192.168.123.1/24
      ip_addresses:
        - address: 192.168.123.2
          nat: True
      storage_type_id: 1
      storage:
        - name: 'HDD-ONE'
          gb: 50
          primary: true
        - name: 'HDD-TWO'
          gb: 50
          primary: false
    - name: VM-REPLICATE
      dns: 91.103.0.1,8.8.8.8
      cpu: 1
      ram: 1
      image_id: 12
      storage_type_id: 1
      replicate: 2
      storage:
        - name: 'HDD-ONE'
          gb: 50
          primary: true

  firewall_rules:
    - allow: true
      source: '*'
      destination: 192.168.132.2/32
      port: '*'
      protocol: 'any'

```
# Settings

`Region`: where IAAS(Infrastructure As A Service) is physically(VMs, VPNs, VRs) stored on servers and routers.

`COP`: where IAAS is soft stored(database).

`Robot`: Every Region has Robot functionality and has an account in its COP.

`validating Region`: It is the Region you are trying to validate its functionality with this software.

`validating COP` : It is the COP where your validating Region is adopted/registered to.

`User account`: One must have an account registered in validating COP to make API requests.

`Robot account`: validating Region is an address and has an account in its COP. 

- `CLOUDCIX_API_URL` - API url for the validating COP.
- `CLOUDCIX_API_USERNAME` - Username of the user account registered in validating COP.
- `CLOUDCIX_API_PASSWORD` - Password of the above user account.
- `CLOUDCIX_API_KEY` - API key provided by the validating COP to the above user.
- `CLOUDCIX_API_VERSION` - Current CloudCIX api version, which is 2.
- `CLOUDCIX_API_V2_URL` - V2 API url for the validating COP.
- `ROBOT_USERNAME` - Validating Region's Robot account username.
- `ROBOT_PASSWORD` - Validating Region's Robot account password
- `ROBOT_API_KEY` - Validating Region's Robot account API key.


All above `CLOUDCIX_API_` and `ROBOT_` fields are required and supplied in settings.py file to run this software smoothly.
These fields can be sorted out from your PAM Operator.
