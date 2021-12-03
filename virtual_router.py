# stdlib
import os
import time
from typing import Any, Dict
from netaddr import IPNetwork
# local
import state
from mixins import HardwareMixin
from utils import get_robot_token
# cloudcix
os.environ['CLOUDCIX_SETTINGS_MODULE'] = 'settings'
from cloudcix import api  # noqa: E402


class VirtualRouter(HardwareMixin):
    """
    Class representing a virtual_router instance on the cloudcix platform.
    """

    obj: Dict[str, Any]
    vpns: list
    project_id: int
    token: str

    def __init__(self, obj: Dict[str, Any], vpns: list, token: str, project_id: int):
        """
        Initialise an instance of the virtual_router class.
        :param obj: The virtual router object created on the CloudCIX platform
        :param vpns: A list of vpns created on the CloudCIX platform for the obj
        :param token: The access token for the cloudcix API.
        :param project_id: The ID of the project related to this virtual_router.
        """
        self.obj = obj
        self.vpns = vpns
        self.token = token
        self.project_id = project_id

    def software_check_build(self):
        """
        Verify that the Virtual Router has been built using the API.
        """

        # while virtual router is building configure other end of vpntunnel if any.
        # so get the vpn details of this(CloudCIX) end.
        for vpn in self.vpns:
            label = 'VPN Tunnel details for configuration'
            print('┌─────────────────────────────────────────────────────────────┐')
            print(f'│{label:^61}│')
            print('├──────────────────────────────┬──────────────────────────────┤')
            print('│           CloudCIX           │            Client            │')
            print('├──────────────────────────────┼──────────────────────────────┤')
            print('│                       Private Network                       │')
            for route in vpn['routes']:
                local_ntw = IPNetwork(dict(route['local_subnet'])['address_range']).cidr
                remote_ntw = IPNetwork(f'{route["remote_subnet"]}').cidr  # just first subnet is enough.
                print(f'│{str(local_ntw):^30}│{str(remote_ntw):^30}│')
            print('├──────────────────────────────┼──────────────────────────────┤')
            print('│                          Public IP                          │')
            print(f'│{self.obj["ip_address"]["address"]:^30}│{vpn["ike_public_ip"]:^30}│')
            print('├──────────────────────────────┼──────────────────────────────┤')
            print('│                        IKE(Phase-1)                         │')
            print(f'│ Authentication               │{vpn["ike_authentication"]:^30}│')
            print(f'│ Encryption                   │{vpn["ike_encryption"]:^30}│')
            print(f'│ Life time(in seconds)        │{vpn["ike_lifetime"]:^30}│')
            print(f'│ Dh_group                     │{vpn["ike_dh_groups"]:^30}│')
            print(f'│ Pre-shared Key               │{vpn["ike_pre_shared_key"]:^30}│')
            print(f'│ Version                      │{vpn["ike_version"]:^30}│')
            print(f'│ Mode                         │{vpn["ike_mode"]:^30}│')
            print('├──────────────────────────────┼──────────────────────────────┤')
            print('│                        IPSec(Phase-2)                       │')
            print(f'│ Authentication               │{vpn["ipsec_authentication"]:^30}│')
            print(f'│ Encryption                   │{vpn["ipsec_encryption"]:^30}│')
            print(f'│ Life time(in seconds)        │{vpn["ipsec_lifetime"]:^30}│')
            print(f'│ Perfect Forward Secrecy(pfs) │{vpn["ipsec_pfs_groups"]:^30}│')
            print(f'│ Establish Tunnel             │{vpn["ipsec_establish_time"]:^30}│')
            print('└──────────────────────────────┴──────────────────────────────┘')
            print()
            print()
            print('Configure Remote end of VPN with above configuration.')
            print()
            a = input('Press enter once VPN configuration completed.')
            print(a)

        # Loop through every minute reading virtual router State
        loop_count = 0
        timeout = time.time() + 30 * 60
        while time.time() < timeout:
            loop_count += 1
            status = api.IAAS.virtual_router.read(token=self.token, pk=self.obj['id']).json()['content']['state']
            if status in [state.REQUESTED, state.BUILDING]:
                print(
                    f'\r - Building Virtual Router #{self.obj["id"]} for project #{self.project_id}{"." * loop_count}',
                    end='',
                )
            elif status == state.UNRESOURCED:
                print(f'\r\033[31m - Error! Virtual Router #{self.obj["id"]} was not built.{" " * 100}\033[0m')
                exit(1)
            elif status == state.RUNNING:
                print(f'\r - Virtual Router #{self.obj["id"]} was built{" " * 100}')
                break
            time.sleep(60)

        if time.time() > timeout:
            print(f'\n\033[91m - Virtual Router #{self.obj["id"]} was not built in time. \033[0m')
            exit(1)

    def hardware_check_build(self):
        """
        Verify that the virtual router has been built using ping.
        """
        # Test ping
        self.ping(type='VirtualRouter', id=self.obj['id'], ip=self.obj['ip_address']['address'], response=True)
        print()
        # if VPN, then test the status from Router

        management_ip, credentials, username = self.find_router_login_details()
        for vpn in self.vpns:
            print(f'VPN #{vpn["id"]} status:')

            # Testing IKE
            data = {
                'user_name': username,
                'server_ip': management_ip,
                'password': credentials,
                'command': f'show security ike security-associations family inet '
                           f'{vpn["ike_public_ip"]} detail | no-more ',
            }
            result = self._router_reponse(data)
            if 'error' in result.keys():
                print(f'\r - Failed to test VPN"s IKE on router. Error: {result["error"]}')
                return
            output = result['output']

            status = False
            line = f'\r - IKE peer {vpn["ike_public_ip"]}'

            if line in output:
                ikes = output[1].split(line)
                ikes.pop(0)
                for ike in ikes:
                    if 'State: UP' in ike and f'Local: {self.obj["ip_address"]["address"]}' in ike:
                        status = True
                        print(line, '\n\r', f'\r{ike}')
                        break
            if status:
                print('\r\033[92m - VPN phase1 is running. \033[0m')
            else:
                print('\r\033[91m - VPN phase1 is not running. \033[0m')

            # Testing IPSec
            data['command'] = f'show security ipsec security-associations vpn-name ' \
                              f'virtual_router-{self.project_id}-vpn-{vpn["stif_number"]}-ipsec-vpn'
            result = self._router_reponse(data)
            if 'error' in result.keys():
                print(f'\r\033[91m - Failed to test VPN"s IPsec on router. Error: {result["error"]} \033[0m')
                return
            output2 = result['output']

            print(f'\r - IPSec', '\n\r', f'\r{output2}')
            if 'Total active tunnels: 0' in output2:
                print(f'\r\033[91m - VPN phase2 is not running. \033[0m')
            else:
                print(f'\r\033[92m - VPN phase2 is running. \033[0m')

    def _router_reponse(self, data):
        """
        send data to the router and analyse the results
        :param data:
        :return: output
        """
        result = {
            'error': None,
            'output': None,
        }
        # read the router until timeout or result found
        timeout = time.time() + 3 * 60
        loop_count = 0
        while time.time() < timeout:
            loop_count += 1
            result = self.fetcher(data)
            if 'output' not in result.keys() and 'error' not in result.keys():
                print(f'\r - Checking the status of VPN from the router {"." * loop_count}', end='')
            else:
                break
            time.sleep(30)
        if time.time() > timeout and 'output' not in result.keys() and 'error' not in result.keys():
            result = {
                'error': 'No response from router.',
            }
        return result

    def software_check_update(self):
        """
        Verify that the virtual_router has been updated using the API and back in a running state.
        """
        # Read until timeout or state is correct
        timeout = time.time() + 10 * 60
        loop_count = 0
        while time.time() < timeout:
            loop_count += 1
            status = api.IAAS.virtual_router.read(token=self.token, pk=self.obj['id']).json()['content']['state']
            if status in [state.RUNNING_UPDATE, state.RUNNING_UPDATING]:
                print(f'\r - Updating Virtual Router #{self.obj["id"]}{"." * loop_count}', end='')
            elif status == state.RUNNING:
                print(f'\r - Virtual Router #{self.obj["id"]} Updated{" " * 100}')
                break
            time.sleep(60)

        if time.time() > timeout:
            print(f'\n\033[91m - Virtual Router #{self.obj["id"]} was not updated. \033[0m')
            exit(1)

    def software_check_delete(self):
        """
        Verify that the virtual_router has been deleted using the API.
        """

        # Read until timeout or state is correct
        timeout = time.time() + 10 * 60
        loop_count = 0
        while time.time() < timeout:
            loop_count += 1
            status = api.IAAS.virtual_router.read(token=self.token, pk=self.obj['id']).json()['content']['state']
            if status in [state.SCRUB, state.SCRUB_PREP]:
                print(f'\r - Deleting Virtual Router #{self.obj["id"]}{"." * loop_count}', end='')
            elif status == state.SCRUB_QUEUE:
                print(f'\r - Virtual Router #{self.obj["id"]} Deleted{" " * 100}')
                break
            time.sleep(60)

        if time.time() > timeout:
            print(f'\n\033[91m - Virtual Router #{self.obj["id"]} was not deleted. \033[0m')
            exit(1)

    def hardware_check_delete(self):
        """
        Verify that the virtual_router has been deleted using ping.
        """

        # Test ping
        self.ping(type='VirtualRouter', id=self.obj['id'], ip=self.obj['ip_address']['address'], response=False)

    def update_token(self, token: str):
        """
        Method to update token.
        Used for when Validator runs exceed 2 hours.
        """

        self.token = token

    def find_router_login_details(self):
        """
        To find the management ip, username and credentials of the Virtual Router's router to access it.
        :return: mgnt_ip: address(ipv6)
        """
        # Read Router to find Management IP
        robot_token = get_robot_token()
        response = api.IAAS.router.read(token=robot_token, pk=self.obj['router_id'])
        management_ip = response.json()['content']['management_ip']
        username = response.json()['content']['username']
        credentials = response.json()['content']['credentials']

        return management_ip, credentials, username
