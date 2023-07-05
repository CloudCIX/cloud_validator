from __future__ import annotations
# stdlib
import os
import random
import yaml
from netaddr import IPAddress, IPNetwork, IPSet
from sys import exit
from typing import Any, Dict, List, Optional
# cloudcix
os.environ['CLOUDCIX_SETTINGS_MODULE'] = 'settings'
from cloudcix import api  # noqa: E402


class Data:
    """
    Class representing the data being sent to the API to create and build a project.
    """

    firewall_rules: List[Dict[str, Any]]
    images: List[Dict[str, Any]]
    project: Dict[str, Any]
    subnets: List[Dict[str, Any]]
    used: List[str]
    vms: List[Dict[str, Any]]
    # api doesn't take empty vpn dict(vpn={}), it can be None(vpn=None) or a dict with key pairs(vpn={'a':'b'})
    vpns: List[Optional[Dict[str, Any]]]

    def __init__(self):
        self.firewall_rules = []
        self.images = []
        self.project = {}
        self.subnets = []
        self.used = []
        self.vms = []
        self.vpns = []

    def add_vm(self):
        """
        Add a new VM to the current data.
        """
        image = random.choice(self.images)
        gateway_subnet = random.choice(self.subnets)
        gateway_ip = self.choose_ip(gateway_subnet['address_range'])
        self.used.append(gateway_ip)
        self.vms.append({
            'image_id': f'{image["id"]}',
            'name': f'New-TestVM-{image["display_name"].replace(" ", "-")}',
            'ram': 1,
            'gateway_subnet': gateway_subnet['address_range'],
            'ip_addresses': [
                {
                    'address': gateway_ip,
                    'nat': True,
                },
            ],
            'dns': '8.8.8.8,8.8.4.4',
            'cpu': 1,
            'storage_type_id': 1,
            'storages': [
                {
                    'primary': True,
                    'name': 'NewHDD',
                    'gb': 50,
                },
            ],
        })

    def add_firewall_rule(self):
        """
        Add a new firewall to the current data.
        """
        subnet = random.choice(self.subnets)
        self.firewall_rules.append(
            {
                'allow': True,
                'source': '91.103.3.36',
                'destination': f'{subnet["address_range"]}',
                'protocol': 'any',
                'debug_logging': False,
                'pci_logging': False,
            },
        )

    def retrieve_images(self, region: str, token: str):
        """
        Method to retrieve all the images in a given region
        """
        params = {
            'search[regions__region]': region,
            'search[enabled]': True,
            'order': 'name',
        }
        response = api.IAAS.image.list(token=token, params=params)
        if response.status_code == 200:
            self.images = response.json()['content']
        # 500 error is known and is under investigation, we are ignoring the effect.
        elif response.status_code == 500:
            pass
        else:
            print('\n\033[91m - There was an error while retrieving images for the region. \033[0m')
            exit(1)

    def choose_ip(self, subnet) -> str:
        """
        Method for selecting an IP for a VM
        """
        ip = ''
        if not subnet:
            # Randomly select subnet
            subnets = [subnet['address_range'] for subnet in self.subnets]
            subnet = random.choice(subnets)

        # Create IP Network and choose IP from valid IPs
        network = IPNetwork(subnet)
        blocked_ips = [network.ip, network.broadcast]
        blocked_ips.extend([IPAddress(used) for used in self.used])
        blocked = IPSet(blocked_ips)
        while not ip or ip in blocked:
            ip = network[random.randint(1, len(network) - 2)]
        return str(ip)

    @classmethod
    def validator_light(cls, region: str, name: str, token: str) -> Data:
        """
        Class method to instantiate an instance of the Data class with set values.
        """

        # Create an instance of the Data class and retrieve the images for the region
        data = cls()
        data.retrieve_images(region=region, token=token)

        # Add project data.
        data.project = {
            'region_id': region,
            'name': name,
        }

        # Add project subnets.
        data.subnets = [{
            'address_range': '192.168.123.1/24',
            'name': 'Test',
        }]

        # Add firewall rules
        data.firewall_rules = [{
            'allow': True,
            'source': '*',
            'destination': '192.168.123.1/24',
            'protocol': 'any',
            'debug_logging': False,
            'pci_logging': False,
        }]

        # Add vpn
        data.vpns = [{
            'description': 'Home',
            'vpn_type': 'site_to_site',
            'ike_authentication': 'sha-384',
            'ike_encryption': 'aes-256-cbc',
            'ike_lifetime': 18000,
            'ike_dh_groups': 'group2',
            'ike_pre_shared_key': 'test',
            'ike_version': 'v1-only',
            'ike_mode': 'main',
            'ike_gateway_type': 'public_ip',
            'ike_gateway_value': '91.103.3.36',
            'ipsec_authentication': 'hmac-sha-256-128',
            'ipsec_encryption': 'aes-256-cbc',
            'ipsec_lifetime': 18000,
            'ipsec_pfs_groups': 'group2',
            'ipsec_establish_time': 'immediately',
            'routes': [{
                'local_subnet': '192.168.123.1/24',
                'remote_subnet': '172.16.32.0/24',
            }],
        }]

        # Get Subnets and used IPs for use in setting VM IPs
        data.used = [subnet['address_range'].split('/')[0] for subnet in data.subnets]

        all_subnets = data.subnets
        # Add VM for each image retrieved
        for image in data.images:
            ip_addresses = []
            gateway_subnet = random.choice(data.subnets)
            gateway_ip = data.choose_ip(gateway_subnet['address_range'])
            ip_addresses.append({
                'address': gateway_ip,
                'nat': True,
            })
            rest_subnets = list(
                filter(
                    lambda sub: sub['address_range'] != gateway_subnet['address_range'],
                    all_subnets,
                ),
            )
            if image['multiple_ips']:
                for sub in rest_subnets:
                    ip = data.choose_ip(sub['address_range'])
                    data.used.append(ip)
                    ip_addresses.append({
                        'address': ip,
                        'nat': False,
                    })

            data.vms.append({
                'image_id': f'{image["id"]}',
                'name': f'TestVM-{image["display_name"].replace(" ", "-")}',
                'ram': 1,
                'gateway_subnet': gateway_subnet['address_range'],
                'ip_addresses': ip_addresses,
                'dns': '8.8.8.8,8.8.4.4',
                'cpu': 1,
                'storage_type_id': 1,
                'storages': [
                    {
                        'primary': True,
                        'name': 'C',
                        'gb': 50,
                    },
                ],
            })

        return data

    @classmethod
    def validator_custom(cls, region: str, file: str, token: str) -> Data:
        """
        Class method to instantiate an instance of the Data class using a YAML file.
        """

        # Load config from file
        with open(f'configs/{file}', 'r') as config:
            config_loaded = yaml.safe_load(config)

        # Create an instance of the Data class and retrieve the images for the region
        data = cls()
        data.retrieve_images(region=region, token=token)

        # Set project data
        data.project = {
            'region_id': region,
            'name': config_loaded['project']['name'],
        }

        data.firewall_rules = config_loaded['firewall_rules']

        # Add Subnets to project
        for subnet in config_loaded['subnets']:
            data.subnets.append({
                'address_range': f'{subnet["gateway"]}/{subnet["mask"]}',
                'name': subnet['name'],
            })

        # Add VPN
        try:
            data.vpns = config_loaded['vpns']
        except KeyError:
            pass

        # Get Subnets and used IPs for use in setting VM IPs
        data.used = []
        data.used = [subnet['gateway'] for subnet in config_loaded['subnets']]
        all_subnets = data.subnets
        # Set VMs for random
        if config_loaded['vms']['random']:
            hd_sizes = [50, 100, 150, 200, 250]
            count = config_loaded['vms']['count']
            for vm in range(count):
                # Get IP Address and image for VM
                image = random.choice(data.images)
                gateway_subnet = config_loaded['vms']['vm_list'][0]['gateway_subnet']
                gateway_ip = data.choose_ip(gateway_subnet)
                data.used.append(gateway_ip)

                ip_addresses = config_loaded['vms']['vm_list'][0]['ip_addresses']
                if len(ip_addresses) > 1 and image['multiple_ips']:
                    rest_subnets = list(
                        filter(
                            lambda sub: sub['address_range'] != gateway_subnet['address_range'],
                            all_subnets,
                        ),
                    )
                    subnet = random.choice(rest_subnets)
                    ip = data.choose_ip(subnet['address_range'])
                    data.used.append(ip)
                    for ip_addr in ip_addresses:
                        if 'address' not in ip_addr.keys():
                            if ip_addr['nat']:
                                ip_addr['address'] = gateway_ip
                            else:
                                ip_addr['address'] = ip
                else:
                    ip_addresses = [{
                        'address': gateway_ip,
                        'nat': True,
                    }]

                # Add the VM
                data.vms.append({
                    'image_id': f'{image["id"]}',
                    'name': f'RandomVM-{image["display_name"].replace(" ", "-")}-{vm}',
                    'ram': random.randint(1, 2),
                    'gateway_subnet': gateway_subnet,
                    'ip_addresses': ip_addresses,
                    'dns': '8.8.8.8,8.8.4.4',
                    'cpu': random.randint(1, 2),
                    'storage_type_id': 1,
                    'storages': [],
                })

                # Add Storage
                for storage in range(random.randint(1, 2)):
                    data.vms[vm]['storages'].append({
                        'primary': storage == 0,
                        'name': f'TestHD-{storage}',
                        'gb': random.choice(hd_sizes),
                    })

        if not config_loaded['vms'].get('vm_list'):
            return data

        for vm_obj in config_loaded['vms']['vm_list']:
            replicate = 1 if not vm_obj.get('replicate') else vm_obj.get('replicate')
            for rep in range(replicate):

                # Get name and ip address for VM
                rep_name = f'{vm_obj["name"]}-{rep}'
                name = rep_name if replicate > 1 else vm_obj['name']
                gateway_ip = data.choose_ip(vm_obj['gateway_subnet'])
                data.used.append(gateway_ip)
                ip_addresses = vm_obj['ip_addresses']
                for ip_addr in ip_addresses:
                    if 'address' not in ip_addr.keys():
                        if ip_addr['nat']:
                            ip_addr['address'] = gateway_ip
                        else:
                            rest_subnets = list(
                                filter(
                                    lambda sub: sub['address_range'] != vm_obj['gateway_subnet'],
                                    all_subnets,
                                ),
                            )
                            subnet = random.choice(rest_subnets)
                            ip = data.choose_ip(subnet['address_range'])
                            ip_addr['address'] = ip
                            data.used.append(ip)

                # Add VM
                data.vms.append({
                    'image_id': f'{vm_obj["image_id"]}',
                    'name': name,
                    'ram': vm_obj['ram'],
                    'gateway_subnet': vm_obj['gateway_subnet'],
                    'ip_addresses': ip_addresses,
                    'dns': vm_obj['dns'],
                    'cpu': vm_obj['cpu'],
                    'storage_type_id': vm_obj['storage_type_id'],
                    'storages': vm_obj['storages'],
                })

        return data

    @classmethod
    def validator_heavy(
            cls,
            region: str,
            name: str,
            token: str,
            cores: int,
            ram: int,
            storage: int,
            unix: bool,
            storage_type_id: int) -> Data:
        """
        Class method to instantiate an instance of the Data class which will fill the region
        """

        # Create an instance of the Data class and retrieve the images for the region
        data = cls()
        data.retrieve_images(region=region, token=token)
        windows_images = [image for image in data.images if image['answer_file_name'] == 'windows']
        unix_images = [
            image for image in data.images if
            image['answer_file_name'] == 'ubuntu' or image['answer_file_name'] == 'centos'
        ]

        # Check that there are images for the chosen region and type
        # Check that there are images for the chosen region and type
        if unix and len(unix_images) == 0:
            exit(0)
        if not unix and len(windows_images) == 0:
            exit(0)

        # Add project data.
        data.project = {
            'region_id': region,
            'name': name,
        }

        # Add project subnets.
        data.subnets = [{
            'address_range': '192.168.123.1/24',
            'name': 'Test',
        }]

        # Add firewall rules
        data.firewall_rules = [{
            'allow': True,
            'source': '*',
            'destination': '192.168.123.1/24',
            'protocol': 'any',
            'debug_logging': True,
            'pci_logging': False,
        }]

        # Get Subnets and used IPs for use in setting VM IPs
        data.used = [subnet['address_range'].split('/')[0] for subnet in data.subnets]

        # Add VM
        subnet = random.choice(data.subnets)
        ip = data.choose_ip(subnet['address_range'])
        data.used.append(ip)
        image = random.choice(unix_images) if unix else random.choice(windows_images)
        data.vms.append({
            'image_id': f'{image["id"]}',
            'name': f'TestVM-{image["display_name"].replace(" ", "-")}',
            'ram': ram,
            'gateway_subnet': subnet['address_range'],
            'ip_addresses': [
                {
                    'address': ip,
                    'nat': True,
                },
            ],
            'dns': '8.8.8.8,8.8.4.4',
            'cpu': cores,
            'storage_type_id': storage_type_id,
            'storages': [
                {
                    'primary': True,
                    'name': 'TestHD',
                    'gb': storage,
                },
            ],
        })

        return data
