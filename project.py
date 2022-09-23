# stdlib
import asyncio
import os
import time
from datetime import datetime
from requests import Response
# local
import state
from dataclasses import Data
from virtual_router import VirtualRouter
from vm import VM
# cloudcix
os.environ['CLOUDCIX_SETTINGS_MODULE'] = 'settings'
from cloudcix import api  # noqa: E402


class Project:
    """
    Class representing a project on the cloudcix platform.
    """

    data: Data
    project_id: int
    region: str
    subnets: list
    token: str
    virtual_router: VirtualRouter
    vms: list

    def __init__(
        self,
        region: str,
        token: str,
        file: str = '',
        heavy: bool = False,
        cores: int = 0,
        ram: int = 0,
        storage: int = 0,
        unix: bool = False,
        storage_type_id: int = 1,
    ):
        """
        Initialise the project with a region and access token.
        :param region: The region in which the project should be built.
        :param token: The access token for the cloudcix api.
        """
        self.region = region
        self.token = token
        timestamp = datetime.now().strftime('%d-%m-%Y--%H-%M-%S.%f')[:-3]
        if file:
            self.data = Data.validator_custom(
                region=self.region,
                file=file,
                token=self.token,
            )
        elif heavy:
            self.data = Data.validator_heavy(
                region=self.region,
                name=f'validator_heavy@{timestamp}',
                token=self.token,
                cores=cores,
                ram=ram,
                storage=storage,
                unix=unix,
                storage_type_id=storage_type_id,
            )
        else:
            self.data = Data.validator_light(
                region=self.region,
                name=f'validator@{timestamp}',
                token=self.token,
            )

    def create(self) -> bool:
        """
        Build the project in the cloud.
        """

        # Create a project with token and data.

        response: Response = api.IAAS.cloud.create(token=self.token, data=vars(self.data))

        if response.status_code == 201:
            content = response.json()['content']
            self.project_id = content['project']['id']
            self.subnets = content['virtual_router']['subnets']
            self.virtual_router = VirtualRouter(
                obj=content['virtual_router'],
                vpns=content['vpns'],
                token=self.token,
                project_id=self.project_id,
            )
            self.vms = [VM(token=self.token, obj=vm) for vm in content['vms']]

        # 500 error is known and is under investigation, we are ignoring the effect.
        elif response.status_code == 500:
            print(f'\033[91m {response} \033[0m')

        else:
            print(f'\033[91m {response.json()} \033[0m')
            exit(1)

        return True

    def check_bandwidth(self):
        """
        Verify that the VMs in a project
        """

        print('┌──────────────────────┐')
        print(f'│{"Checking Bandwidth":^22}│')
        print('└──────────────────────┘')
        print()

        # Verify VMs build using API
        failures = [vm.check_bandwidth() for vm in self.vms].count(False)
        if failures:
            print(f'{failures} VMs failed the bandwidth test')
        print()

    def check_create(self):
        """
        Verify that the project Virtual Router and VMs are successfully built.
        """

        print('┌──────────────────────┐')
        print(f'│{"Building":^22}│')
        print('└──────────────────────┘')
        print()

        # Verify Virtual Router build using API
        self.virtual_router.software_check_build()

        # Verify VMs build using API
        success = [vm.software_check_build() for vm in self.vms]
        if not all(success):
            exit(1)
        print()

        # Verify the Virtual Router build using ping
        self.virtual_router.hardware_check_build()

        # Verify the VMs build using ping/rdp
        for vm in self.vms:
            vm.hardware_check_build()

        print()

    def restart(self):
        """
        Restart the project in the cloud.
        Changes state to stopping (5) and then to starting (7).
        """

        print('┌──────────────────────┐')
        print(f'│{"Restarting":^22}│')
        print('└──────────────────────┘')
        print()

        for vm in self.vms:
            print(f'\033[36m - Restarting VM #{vm.obj["id"]}\033[0m')

            # Stop VM and verify state.
            vm.stop()
            vm.software_check_stopped()
            vm.hardware_check_stopped()

            # Start VM and verify state
            vm.start()
            vm.software_check_started()
            vm.hardware_check_started()

            print()

    def update(self):
        """
        Update the project in the cloud.
        """

        print('┌──────────────────────┐')
        print(f'│{"Updating":^22}│')
        print('└──────────────────────┘')
        print()

        # Store VM IDs in data
        for v in self.data.vms:
            for vm in self.vms:
                if vm.obj['name'] == v['name']:
                    v['id'] = vm.obj['id']
                    # Store storage IDs in data
                    for storage in v['storages']:
                        for vm_storage in vm.obj['storages']:
                            if vm_storage['name'] == storage['name']:
                                storage['vm_id'] = vm_storage['vm_id']
                                storage['id'] = vm_storage['id']
                                break
                    # Store ip addresses IDs in data
                    for ip in v['ip_addresses']:
                        for vm_ip in vm.obj['ip_addresses']:
                            if vm_ip['address'] == ip['address']:
                                ip['id'] = vm_ip['id']
                                break
                    break

        # Store VPN IDs in data
        for v in self.data.vpns:
            for vpn in self.virtual_router.vpns:
                if vpn['description'] == v['description']:
                    v['id'] = vpn['id']
                    break

        # Store subnet IDs in data
        for s in self.data.subnets:
            for subnet in self.subnets:
                if s['address_range'] == subnet['address_range']:
                    s['id'] = subnet['id']
                    s['address_id'] = subnet['address_id']
                    s['vlan'] = subnet['vlan']
                    s['vxlan'] = subnet['vxlan']

        # Updating only virtual_router and test if VM restarts by the state from database
        print('\r  Updating the virtual_router only and testing if VM restarts')
        self.data.add_firewall_rule()
        update = api.IAAS.cloud.update(token=self.token, pk=self.project_id, data=vars(self.data))
        if update.status_code == 200:

            vms = [VM(token=self.token, obj=vm.obj) for vm in self.vms]
            # ping check VMs for 5min
            # asyncio.run(self.main(vms))

            # db state check
            for vm in vms:
                print(f'\r - Checking the state of VM # {vm.obj["id"]} from database')
                vm.sofware_check_state()
        else:
            print(update.content)
            print(update.json())
            exit(1)

        print('\r  Checking the virtual_router has updated before proceeding')
        # Verify Virtual Router updated using API
        self.virtual_router.software_check_update()

        # Update the data and send request for update
        existing_vm_count = len(vms)
        self.data.add_vm()
        # Updating only virtual_router and test if VM restarts by the state from database
        print('\r  Adding VM to project')
        update = api.IAAS.cloud.update(token=self.token, pk=self.project_id, data=vars(self.data))

        params = {'project_id': self.project_id, 'exclude[id__in]': [vm.obj['id'] for vm in self.vms]}

        response = api.IAAS.vm.list(token=self.token, params=params)
        if response.status_code == 200:
            vms = response.json()['content']
        else:
            print(response.status_code)
            print(response.json())
            exit()

        self.vms.extend([VM(token=self.token, obj=vm) for vm in vms])

        if update.status_code == 200:

            old_vms = self.vms[:existing_vm_count]
            new_vms = self.vms[existing_vm_count:]

            # Verify VMs were updated using api
            for vm in old_vms:
                vm.software_check_updating()
            print()

            # Verify VMs build using API
            success = [vm.software_check_build() for vm in new_vms]
            if not all(success):
                exit(1)
            print()

            # Verify the VMs build using ping/rdp
            for vm in new_vms:
                vm.hardware_check_build()
        else:
            print(update.status_code)
            print(update.json())
            exit(1)

        print()

    def delete(self):
        """
        Delete the project from the cloud.
        """

        print('┌──────────────────────┐')
        print(f'│{"Deleting":^22}│')
        print('└──────────────────────┘')
        print()

        # Delete project from cloud
        data = {'state': state.SCRUB}
        response = api.IAAS.project.partial_update(token=self.token, pk=self.project_id, data=data)

        # Server response is successful
        if response.status_code == 200:

            # Check if virtual_router, VMs and Project are deleted.
            self.virtual_router.software_check_delete()

            for vm in self.vms:
                vm.software_check_delete()
                vm.hardware_check_delete()

            self.check_delete()

            print(f'\033[32m - Project #{self.project_id} was successfully deleted via the API.\033[0m')

        elif response.status_code == 400 and 'errors' in response.json():
            print(response.json())
        else:
            print(response.status_code)
            print(response.json())
            exit()

        print()

    def check_delete(self):
        """
        Check if project has been deleted.
        """

        timeout = time.time() + 20 * 60
        loop_count = 0

        # Read until response shows correct state
        while time.time() < timeout:
            loop_count += 1
            response = api.IAAS.project.read(token=self.token, pk=self.project_id)
            if response.status_code == 200:
                project = response.json()['content']
            else:
                print(response.status_code)
                print(response.json())
                exit()
            print(f'\r - Marking Project #{self.project_id} for deletion.{"." * loop_count}', end='')
            if project['shut_down']:
                print(f'\r\033[32m - Successfully marked Project #{self.project_id} for deletion.{" " * 50}\033[0m')
                break
            time.sleep(60)

        if time.time() > timeout:
            print(f'\r\033[91m - Project #{self.project_id} was unsuccessfully deleted.{" " * 100} \033[0m')
            exit(1)

    def update_token(self, token: str):
        """
        Method for updating tokens of project, vms and virtual_router.
        Used for when Validator runs exceed 2 hours.
        """

        self.token = token
        self.virtual_router.update_token(token=token)

        for vm in self.vms:
            vm.update_token(token=token)

    @staticmethod
    async def main(vms):
        """
        Runs all vms Ping check parallel.
        """
        # ping check VMs for 5min
        await asyncio.gather(*(vm.hardware_check_state() for vm in vms))
