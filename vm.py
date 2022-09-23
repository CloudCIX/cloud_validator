# stdlib
import asyncio
import os
import time
from typing import Any, Dict
# local
from mixins import HardwareMixin
import state
# cloudcix
os.environ['CLOUDCIX_SETTINGS_MODULE'] = 'settings'
from cloudcix import api  # noqa: E402


class VM(HardwareMixin):
    """
    Class representing a VM instance on the cloudcix platform.
    """
    obj: Dict[str, Any]
    phantom: bool
    token: str

    def __init__(self, token: str, obj: Dict[str, Any]):
        """
        Initialise an instance of the VM class.
        :param token: The API token used to connect to cloudcix API.
        :param id: The ID of the VM on the cloudcix platform.
        """
        self.token = token
        self.obj = obj
        self.phantom = self.obj['image']['display_name'] == 'Manual'

    def stop(self):
        """
        Stop the VM.
        """

        response = api.IAAS.vm.partial_update(token=self.token, pk=self.obj['id'], data={'state': state.QUIESCE})
        if not response.status_code == 200:
            print(response.json())
            exit(1)

    def start(self):
        """
        Start the VM
        """

        response = api.IAAS.vm.partial_update(token=self.token, pk=self.obj['id'], data={'state': state.RESTART})
        if not response.status_code == 200:
            print(response.json())
            exit(1)

    def software_check_updating(self):
        """
        Verify that a VM moves through the correct states when updated.
        """

        loop_count = 0
        timeout = time.time() + 480 * 60

        image = self.obj['image']['display_name']
        # Loop through every minute reading VM state
        while time.time() < timeout:
            loop_count += 1

            response = api.IAAS.vm.read(token=self.token, pk=self.obj['id'])
            if response.status_code == 200:
                status = response.json()['content']['state']
            else:
                print(response.status_code)
                print(response.json())
                exit()

            if status == state.UPDATE:
                print(f'\r - VM #{self.obj["id"]} ({image}) update requested{"." * loop_count}{" " * 100}', end='')
            elif status == state.UPDATING:
                print(f'\r - VM #{self.obj["id"]} ({image}) is updating{"." * loop_count}{" " * 100}', end='')
            elif status == state.RUNNING:
                print(f'\r - VM #{self.obj["id"]} ({image}) was updated and is running!{" " * 100}')
                break
            else:
                print(f'\r\033[31m - Error! VM #{self.obj["id"]} ({image}) was not updated.{" " * 100}\033[0m')
                exit(1)

            # Sleep for 60 seconds
            time.sleep(60)

        if time.time() > timeout:
            print(f'\n\033[91m - VM #{self.obj["id"]} ({image}) was not updated in time. \033[0m')
            exit(1)

    def software_check_build(self) -> bool:
        """
        Verify that the VM has been built on the cloudcix platform using API.
        """

        loop_count = 0
        timeout = time.time() + 480 * 60
        success = False

        image = self.obj['image']['display_name']

        # Loop through every minute reading VM state
        while time.time() < timeout:
            loop_count += 1

            response = api.IAAS.vm.read(token=self.token, pk=self.obj['id'])
            if response.status_code == 200:
                status = response.json()['content']['state']
            else:
                print(response.status_code)
                print(response.json())
                exit()

            if status in [state.REQUESTED, state.BUILDING]:
                print(f'\r - Building VM #{self.obj["id"]} with image \'{image}\'{"." * loop_count}', end='')
            elif status == state.UNRESOURCED:
                print(
                    f'\r\033[31m - Error! VM #{self.obj["id"]} was not built with image \'{image}\'.{" " * 100}\033[0m',
                )
                exit(1)
            elif status == state.RUNNING:
                print(f'\r - VM #{self.obj["id"]} was built with image \'{image}\'!{" " * 100}')
                success = True
                break
            # Sleep for 60 seconds
            time.sleep(60)

        if time.time() > timeout:
            print(f'\n\033[91m - VM #{self.obj["id"]} was not built with image \'{image}\' in time. \033[0m')

        return success

    def hardware_check_build(self):
        """
        Verify that the VM has been built on the cloudcix platform using ping.
        """
        if self.phantom:
            print(
                f'\r\033[91m - VM #{self.obj["id"]} ({self.ob["image"]["display_name"]}) is phantom, '
                f'sleeping for 1 minute.{" " * 100} \033[0m',
            )
            time.sleep(60)
            return

        public_ip = None

        for private_ip in self.obj['ip_addresses']:
            if private_ip['public_ip'] is not None:
                public_ip = private_ip['public_ip']['address']
                break

        if not public_ip:
            print(
                f'\r\033[91m - VM #{self.obj["id"]} does not have a public ip, '
                f'sleeping for 1 minute.{" " * 100} \033[0m',
            )
            time.sleep(60)
            return

        self.ping(type='VM', id=self.obj['id'], ip=public_ip, response=True)

    def check_bandwidth(self):
        public_ip = None

        for private_ip in self.obj['ip_addresses']:
            if private_ip['public_ip'] is not None:
                public_ip = private_ip['public_ip']['address']
                break

        if not public_ip:
            print(
                f'\r\033[91m - VM #{self.obj["id"]} does not have a public ip, '
                f'sleeping for 1 minute.{" " * 100} \033[0m',
            )
            time.sleep(60)
            return

        return self.stress_test(public_ip, vm_id=self.obj['id'])

    def software_check_stopped(self):
        """
        Verify that the VM has stopped using the API.
        """

        timeout = time.time() + 480 * 60
        loop_count = 0

        image = self.obj['image']['display_name']

        # Read until timeout or response shows correct state
        while time.time() < timeout:
            loop_count += 1

            response = api.IAAS.vm.read(token=self.token, pk=self.obj['id'])
            if response.status_code == 200:
                status = response.json()['content']['state']
            else:
                print(response.status_code)
                print(response.json())
                exit()

            if status in [state.QUIESCE, state.QUIESCING]:
                print(f'\r - Stopping VM #{self.obj["id"]} ({image}){"." * loop_count}', end='')
            elif status == state.QUIESCED:
                print(f'\r - VM #{self.obj["id"]} ({image}) stopped.{" " * 100}')
                break
            time.sleep(5)

        if time.time() > timeout:
            print(f'\r\033[91m - VM #{self.obj["id"]} ({image}) was not stopped.{" " * 100} \033[0m')
            exit(1)

    def software_check_started(self):
        """
        Verify that the VM has started using the API.
        """

        timeout = time.time() + 480 * 60
        loop_count = 0

        image = self.obj['image']['display_name']

        # Read until response shows correct state
        while time.time() < timeout:
            loop_count += 1

            response = api.IAAS.vm.read(token=self.token, pk=self.obj['id'])
            if response.status_code == 200:
                status = response.json()['content']['state']
            else:
                print(response.status_code)
                print(response.json())
                exit()

            if status in [state.RESTART, state.RESTARTING]:
                print(f'\r - Starting VM #{self.obj["id"]} ({image}){"." * loop_count}', end='')
            elif status == state.RUNNING:
                print(f'\r - VM #{self.obj["id"]} ({image}) started.{" " * 100}')
                break

            time.sleep(5)

        if time.time() > timeout:
            print(f'\r\033[91m - VM #{self.obj["id"]} ({image}) was not started.{" " * 100} \033[0m')
            exit(1)

    def hardware_check_stopped(self):
        """
        Verify that the VM has stopped using ping.
        """
        if self.phantom:
            print(
                f'\r\033[91m - VM #{self.obj["id"]} ({self.ob["image"]["display_name"]}) is phantom,'
                f' sleeping for 1 minute.{" " * 100} \033[0m',
            )
            time.sleep(60)
            return

        for private_ip in self.obj['ip_addresses']:
            if private_ip['public_ip'] is not None:
                public_ip = private_ip['public_ip']['address']
                break

        if not public_ip:
            print(
                f'\r\033[91m - VM #{self.obj["id"]} does not have a public ip, '
                f'sleeping for 1 minute.{" " * 100} \033[0m',
            )
            time.sleep(60)
            return

        self.ping(type='VM', id=self.obj['id'], ip=public_ip, response=False)

    def hardware_check_started(self):
        """
        Verify that the VM has started using ping
        """
        if self.phantom:
            print(
                f'\r\033[91m - VM #{self.obj["id"]} ({self.ob["image"]["display_name"]}) is phantom, '
                f'sleeping for 1 minute.{" " * 100} \033[0m',
            )
            time.sleep(60)
            return

        public_ip = None

        for private_ip in self.obj['ip_addresses']:
            if private_ip['public_ip'] is not None:
                public_ip = private_ip['public_ip']['address']

        if not public_ip:
            print(
                f'\r\033[91m - VM #{self.obj["id"]} does not have a public ip, '
                f'sleeping for 1 minute.{" " * 100} \033[0m',
            )
            time.sleep(60)
            return

        self.ping(type='VM', id=self.obj['id'], ip=public_ip, response=True)

    def software_check_delete(self):
        """
        Verify that the VM has been deleted on the cloudcix platform using the API.
        """

        loop_count = 0
        timeout = time.time() + 480 * 60

        image = self.obj['image']['display_name']

        # Read until timeout or state is correct
        while time.time() < timeout:
            loop_count += 1

            response = api.IAAS.vm.read(token=self.token, pk=self.obj['id'])
            if response.status_code == 200:
                status = response.json()['content']['state']
            else:
                print(response.status_code)
                print(response.json())
                exit()

            if status in [state.SCRUB, state.SCRUB_PREP]:
                print(f'\r - Deleting VM #{self.obj["id"]} ({image}){"." * loop_count}', end='')
            elif status == state.SCRUB_QUEUE:
                print(
                    f'\r\033[92m - VM #{self.obj["id"]} ({image}) successfully marked for deletion!{" " * 100}\033[0m',
                )
                break
            time.sleep(60)

        if time.time() > timeout:
            print(f'\r\033[91m - VM #{self.obj["id"]} ({image}) was not deleted.{" " * 100} \033[0m')
            exit(1)

    def hardware_check_delete(self):
        """
        Verify that the VM has been deleted on the cloudcix platform using ping.
        """
        if self.phantom:
            print(
                f'\r\033[91m - VM #{self.obj["id"]} ({self.ob["image"]["display_name"]}) is phantom, '
                f'sleeping for 1 minute.{" " * 100} \033[0m',
            )
            time.sleep(60)
            return

        public_ip = None

        for private_ip in self.obj['ip_addresses']:
            if private_ip['public_ip'] is not None:
                public_ip = private_ip['public_ip']['address']
                break

        if not public_ip:
            print(
                f'\r\033[91m - VM #{self.obj["id"]} does not have a public ip, '
                f'sleeping for 1 minute.{" " * 100} \033[0m',
            )
            time.sleep(60)
            return

        self.ping(type='VM', id=self.obj['id'], ip=public_ip, response=False)

    def update_token(self, token: str):
        """
        Method to update token.
        Used for when Validator runs exceed 2 hours.
        """

        self.token = token

    def sofware_check_state(self):
        """
        Used to check if VM is in running state.
        """
        response = api.IAAS.vm.read(token=self.token, pk=self.obj['id'])
        if response.status_code == 200:
            vm_state = response.json()['content']['state']
        else:
            print(response.status_code)
            print(response.json())
            exit()
        # Verify the VMs status using ping/rdp
        if vm_state != state.RUNNING:
            exit(1)
        print(f'\r - VM is in Running state.{" " * 100}')

    async def hardware_check_state(self):
        """
        Pings the VMs for 5min and check if VMs are replying or not.
        """
        if self.phantom:
            print(
                f'\r\033[91m - VM #{self.obj["id"]} ({self.ob["image"]["display_name"]}) is phantom, '
                f'sleeping for 1 minute.{" " * 100} \033[0m',
            )
            time.sleep(60)
            return

        for private_ip in self.obj['ip_addresses']:
            if private_ip['public_ip'] is not None:
                public_ip = private_ip['public_ip']['address']
                break

        if not public_ip:
            print(
                f'\r\033[91m - VM #{self.obj["id"]} does not have a public ip, '
                f'sleeping for 1 minute.{" " * 100} \033[0m',
            )
            return

        print(f'\r - Pinging the VM # {self.obj["id"]}')
        timeout = time.time() + 5 * 60
        loop_count = 0

        while time.time() < timeout:
            loop_count += 1
            self.ping(type='VM', id=self.obj['id'], ip=public_ip, response=True)
            await asyncio.sleep(10)
