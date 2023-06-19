# stdlib
import os
import time
from typing import Any, Dict
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

        # VPN Tunnels verification tests are separated and are not available in this version.

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
            if status in [state.UPDATE, state.UPDATING]:
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
