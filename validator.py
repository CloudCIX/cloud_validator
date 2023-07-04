# stdlib
import getpass
import os
import sys
import random
from typing import Any, Dict, List, Union
# local
from project import Project
from utils import get_robot_token
# cloudcix
os.environ['CLOUDCIX_SETTINGS_MODULE'] = 'settings'
from cloudcix import api  # noqa: E402
from cloudcix.auth import get_admin_token  # noqa: E402


def region_validator(password):
    """
    List all regions and give provide options to validate.

    Those options include:
        - Validator Light - Build a single project.
        - Validator Heavy - Build many projects.
        - Validator Custom - Build a custom project.
    """

    # Get the list of Regions
    token = get_admin_token()
    robot_token = get_robot_token()
    params = {'search[cloud_region]': True, 'order': 'id'}
    response = api.Membership.address.list(token=token, params=params)
    if response.status_code != 200:
        print(
            f'HTTP Error {response.status_code} occurred while trying to list instances of Membership.address with the',
            f' following params: {params}.\nResponse from API: {response.content.decode()}',
        )
        exit(1)

    addresses = response.json()['content']
    # Display the regions
    valid_ids = set()
    print()
    print('┌────────────────────────────────────────────────────────────────┐')
    print('│                     Available Regions                          │')
    print('├────────┬───────────────────────────────────────────────────────┤')
    print('│   ID   │                       Name                            │')
    print('├────────┼───────────────────────────────────────────────────────┤')
    for address in addresses:
        print(f'│{address["id"]:^8}│{address["name"]:^55}│')
        valid_ids.add(str(address['id']))
    print('└────────┴───────────────────────────────────────────────────────┘')
    region = input("\nID of the Robot's region to validate: ")
    print()

    if region not in valid_ids:
        print(f'Invalid region (#{region}). Please try again.')
        exit(1)

    # Hardware information
    os.system('clear')
    get_servers(region, token)
    project_count = get_projects(region, robot_token)

    # Provide options for what to do
    print('\nWhat would you like to run?')
    print('1. Validator Light')
    print('2. Validator Custom')
    if project_count == 0:
        print('3. Validator Heavy')
    option = int(input('\nID of option to run: '))
    if option == 1:
        print('\nRunning Validator Light')
        validator_light(region=region)
    elif option == 2:
        print('\nRunning Validator Custom')
        validator_custom(region=region)
    elif option == 3 and project_count == 0:
        print('\nRunning Validator Heavy')
        validator_heavy(region=region)
    else:
        print(f'\nInvalid option "{option}" selected. Please try again.')
        exit(1)


def validator_light(region: str):
    """
    Validator Light:

    Steps:
        1. Build a project.
        2. Restart a project.
        3. Update a project.
        4. Delete a project.
    """

    # Clear terminal window
    os.system('clear')
    token = get_admin_token()
    project = Project(region=region, token=token)
    project.create()
    project.check_create()
    project.restart()
    project.update()
    project.delete()


def validator_custom(region: str):
    """
    Validator Custom:

    Steps - for each file in config directory:
        1. Build a project.
        2. Restart a project.
        3. Update a project.
        4. Delete a project.
    """

    # Clear terminal window
    os.system('clear')
    token = get_admin_token()
    configs = {i + 1: f for i, f in enumerate(os.listdir('configs')) if os.path.isfile(os.path.join('configs', f))}
    for conf in configs:
        print(f'{conf}. {configs[conf]}')
    choice = int(input('\nWhich configuration would you like to run: '))
    selected = configs.get(choice)
    if not selected:
        print('\nYou did not select a valid configuration.')
        exit(1)
    os.system('clear')
    project = Project(region=region, token=token, file=selected)
    project.create()
    project.check_create()
    project.check_bandwidth()
    project.restart()
    project.delete()


def validator_heavy(region: str):
    """
    Validator Heavy:

    Steps:
        1. Build many projects to fill a region.
        2. Restart the projects.
        3. Update the projects.
        4. Delete the projects.
    """

    # Clear terminal window
    os.system('clear')
    robot_token = get_robot_token()

    # Oversubscription Value
    OVERSUBSCRIPTION_VALUE = 8

    # Limit Variables
    DISK_BASE_LIMIT = 100
    RAM_BASE_LIMIT = 8
    CPU_CREATE_LIMIT = 0.77
    DISK_CREATE_LIMIT = 0.77
    RAM_CREATE_LIMIT = 0.77
    CPU_UPDATE_LIMIT = 1.00
    DISK_UPDATE_LIMIT = 0.9
    RAM_UPDATE_LIMIT = 0.95


    # Get region hardware
    params = {'search[region_id]': region, 'search[enabled]': True}
    response = api.IAAS.server.list(token=robot_token, params=params)
    if response.status_code == 200:
        servers = response.json()['content']
    else:
        print(response.status_code)
        print(response.json())
        exit()

    # Sum region hardware windows hdd
    cores_windows_hdd = sum([
        server['cores'] * OVERSUBSCRIPTION_VALUE * CPU_CREATE_LIMIT
        for server in servers
        if server['type']['id'] == 1 and server['storage_type']['id'] == 1
    ])
    ram_windows_hdd = sum([
        (server['ram'] - RAM_BASE_LIMIT) * RAM_CREATE_LIMIT
        for server in servers
        if server['type']['id'] == 1 and server['storage_type']['id'] == 1
    ])
    storage_windows_hdd = sum([
        (server['gb'] - DISK_BASE_LIMIT) * DISK_CREATE_LIMIT
        for server in servers
        if server['type']['id'] == 1 and server['storage_type']['id'] == 1
    ])

    # Sum region hardware windows ssd
    cores_windows_ssd = sum([
        server['cores'] * OVERSUBSCRIPTION_VALUE * CPU_CREATE_LIMIT
        for server in servers
        if server['type']['id'] == 1 and server['storage_type']['id'] == 2
    ])
    ram_windows_ssd = sum([
        (server['ram'] - RAM_BASE_LIMIT) * RAM_CREATE_LIMIT
        for server in servers
        if server['type']['id'] == 1 and server['storage_type']['id'] == 2
    ])
    storage_windows_ssd = sum([
        (server['gb'] - DISK_BASE_LIMIT) * DISK_CREATE_LIMIT
        for server in servers
        if server['type']['id'] == 1 and server['storage_type']['id'] == 2
    ])

    # Sum region hardware unix hdd
    cores_unix_hdd = sum([
        server['cores'] * OVERSUBSCRIPTION_VALUE * CPU_CREATE_LIMIT
        for server in servers
        if server['type']['id'] == 2 and server['storage_type']['id'] == 1
    ])
    ram_unix_hdd = sum([
        (server['ram'] - RAM_BASE_LIMIT) * RAM_CREATE_LIMIT
        for server in servers
        if server['type']['id'] == 2 and server['storage_type']['id'] == 1
    ])
    storage_unix_hdd = sum([
        (server['gb'] - DISK_BASE_LIMIT) * DISK_CREATE_LIMIT
        for server in servers
        if server['type']['id'] == 2 and server['storage_type']['id'] == 1
    ])

    # Sum region hardware unix ssd
    cores_unix_ssd = sum([
        server['cores'] * OVERSUBSCRIPTION_VALUE * CPU_CREATE_LIMIT
        for server in servers
        if server['type']['id'] == 2 and server['storage_type']['id'] == 2
    ])
    ram_unix_ssd = sum([
        (server['ram'] - RAM_BASE_LIMIT) * RAM_CREATE_LIMIT
        for server in servers
        if server['type']['id'] == 2 and server['storage_type']['id'] == 2
    ])
    storage_unix_ssd = sum([
        (server['gb'] - DISK_BASE_LIMIT) * DISK_CREATE_LIMIT
        for server in servers
        if server['type']['id'] == 2 and server['storage_type']['id'] == 2
    ])

    # Print out server stats
    print('┌──────────────────────────────────────────────────────────────┐')
    print('│                         Server Stats                         │')
    print('├───────────────────┬─────────┬──────────┬──────────┬──────────┤')
    print('│    Server Type    │  Cores  │ RAM (GB) │ HDD (GB) │ SSD (GB) │')
    print('├───────────────────┼─────────┼──────────┼──────────┼──────────┤')
    line = (
        f'│{"Windows + HDD":^19}│'
        f'{cores_windows_hdd:^9}│'
        f'{ram_windows_hdd:^10}│'
        f'{storage_windows_hdd:^10}│'
        f'{"0":^10}│'
    )
    print(line)
    print('├───────────────────┼─────────┼──────────┼──────────┼──────────┤')
    line = (
        f'│{"Windows + SSD":^19}│'
        f'{cores_windows_ssd:^9}│'
        f'{ram_windows_ssd:^10}│'
        f'{"0":^10}│'
        f'{storage_windows_ssd:^10}│'
    )
    print(line)
    print('├───────────────────┼─────────┼──────────┼──────────┼──────────┤')
    line = (
        f'│{"Unix + HDD":^19}│'
        f'{cores_unix_hdd:^9}│'
        f'{ram_unix_hdd:^10}│'
        f'{storage_unix_hdd:^10}│'
        f'{"0":^10}│'
    )
    print(line)
    print('├───────────────────┼─────────┼──────────┼──────────┼──────────┤')
    line = (
        f'│{"Unix + SSD":^19}│'
        f'{cores_unix_ssd:^9}│'
        f'{ram_unix_ssd:^10}│'
        f'{"0":^10}│'
        f'{storage_unix_ssd:^10}│'
    )
    print(line)
    print('└───────────────────┴─────────┴──────────┴──────────┴──────────┘')
    print()

    # Project types
    types: List[Dict[str, Union[int, bool]]] = [
        {'unix': False, 'storage_type_id': 1},
        {'unix': False, 'storage_type_id': 2},
        {'unix': True, 'storage_type_id': 1},
        {'unix': True, 'storage_type_id': 2},
    ]

    projects: List[Project] = []

    while len(types) > 0:
        selected_type = random.choice(types)
        try:
            token = get_admin_token()
            project = Project(region=region, token=token, file='', heavy=True, cores=1, ram=1, storage=50, **selected_type)  # type: ignore # noqa
            project.create()
            projects.append(project)
        except SystemExit:
            storage = 'HDD' if selected_type['storage_type_id'] == 1 else 'SSD'
            print(f'\n - Projects of this type have errored out. Unix: {selected_type["unix"]}; Storage: {storage}')
            print()
            # remove type from list
            types.remove(selected_type)
            

    for project in projects:
        new_token = get_admin_token()
        project.update_token(token=new_token)
        project.check_create()

    # List VMs using robot token
    robot_token = get_robot_token()
    # Exclude VMs in the Closed State (99)
    params = ('exclude[state]': 99)
    response = api.IAAS.vm.list(token=robot_token, params=params)
    if response.status_code == 200:
        vms = response.json()['content']
    else:
        print(response.status_code)
        print(response.json())
        exit()

    servers_vms = {
        server['id']: [vm for vm in vms if vm['server_id'] == server['id']]
        for server in servers
    }

    # Calculate total utilised
    print('┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐')
    print('│                                           Server Utilisation                                         │')
    print('├───────────────────┬─────────────────────────┬──────────────────┬──────────────────┬──────────────────┤')
    print('│       Server      │          Cores          │        RAM       │        HDD       │        SSD       │')
    print('├───────────────────┼─────────────────────────┼──────────────────┼──────────────────┼──────────────────┤')
    for server in servers:
        id = server['id']
        vms = servers_vms[id]
        server_used_cores = sum([vm['cpu'] for vm in vms])
        server_used_ram = sum([vm['ram'] for vm in vms])
        server_used_ssd = sum([
            storage['gb']
            for vm in vms
            for storage in vm['storages']
            if vm['server_id'] == id and server['storage_type']['id'] == 2
        ])
        server_used_hdd = sum([
            storage['gb']
            for vm in vms
            for storage in vm['storages']
            if vm['server_id'] == id and server['storage_type']['id'] == 1
        ])
        percent_cores = round(server_used_cores / (server['cores'] * OVERSUBSCRIPTION_VALUE) * 100, 3)
        percent_ram = round(server_used_ram / server['ram'] * 100, 3)
        percent_hdd = round(server_used_hdd / server['gb'] * 100, 3) if server['storage_type']['id'] == 1 else 0
        percent_ssd = round(server_used_ssd / server['gb'] * 100, 3) if server['storage_type']['id'] == 2 else 0
        line = (
            f'│{server["id"]:^19}│'
            f'{str(percent_cores) + "% - " + str(server_used_cores) + " cores":^25}│'
            f'{str(percent_ram) + "% - " + str(server_used_ram) + "GB":^18}│'
            f'{str(percent_hdd) + "% - " + str(server_used_hdd) + "GB":^18}│'
            f'{str(percent_ssd) + "% - " + str(server_used_ssd) + "GB":^18}│'
        )
        print(line)
    print('└───────────────────┴─────────────────────────┴──────────────────┴──────────────────┴──────────────────┘')
    print()

    for method in ['restart', 'delete']:
        for project in projects:
            try:
                new_token = get_admin_token()
                project.update_token(token=new_token)
                getattr(project, method)()
            except SystemExit:
                print('\nContinuing exceution.')
                print()


def get_servers(region: str, token: str):
    """
    Retrieve the servers in a given region.
    :param region: The region from which to retrieve the servers.
    :param token: The API access token for the cloudcix API.
    """

    # Get the Router and Servers data from database
    params = {'search[region_id]': region}
    response = api.IAAS.server.list(token=token, params=params)
    if response.status_code != 200:
        print(
            f'HTTP Error {response.status_code} occurred while trying to list instances of IAAS.server with the ',
            f'following params: {params}.\nResponse from API: {response.content.decode()}',
        )
        exit(1)

    servers = response.json()['content']
    if len(servers) == 0:
        print(f'\033[91m No Servers found in region #{region} \033[0m')
        return
    else:
        # Fetch the servers and assets from the API
        asset_tags = list(set(server['asset_tag'] for server in servers if server['asset_tag'] is not None))
        asset_params = {'assetTag__in': asset_tags, 'idAddress': region}
        response = api.Asset.asset.list(token=token, params=asset_params)
        if response.status_code != 200:
            print(
                f'HTTP Error {response.status_code} occurred while trying to list instances of Asset.asset with the ',
                f'following params: {asset_params}.\nResponse from API: {response.content.decode()}',
            )
        else:
            assets: List[Dict[str, Any]] = response.json()['content']

        asset_map = {}
        for asset in assets:
            asset_map[asset['asset_tag']] = (asset['assetTag'], asset['location'].replace(' ', ''))

        label = f'Servers in region #{region}'
        print('\r', end='')  # Remove the loading message
        print('┌────────────────────────────────────────────────────────────────────────────────────────┐')
        print(f'│{label:^88}│')
        print('├───────────┬───────┬──────────┬──────────┬──────────┬───────────┬──────────────┬────────┤')
        print('│   Model   │ Host  │ RAM (GB) │ HDD (GB) │ SSD (GB) │ Asset Tag │   Location   │  Type  │')
        print('├───────────┼───────┼──────────┼──────────┼──────────┼───────────┼──────────────┼────────┤')
        for server in servers:
            asset_tag, location = asset_map.get(server['asset_tag'], ('?', '?'))
            host = 'Yes' if server['host'] else 'No'
            server_type = 'HyperV' if server['type'] == 1 else 'KVM'
            print(
                f'│{server["model"]:^11}│{host:^7}│{server["ram"]:^10}│{server["hdd"]:^10}│'
                f'{server["flash"]:^10}│{asset_tag:^11}│{location:^14}│{server_type:^8}│',
            )
        print('└───────────┴───────┴──────────┴──────────┴──────────┴───────────┴──────────────┴────────┘')

def get_projects(region: str, token: str) -> int:
    """
    Retrieve the projects in a given region.
    :param region: The region from which to retrieve the projects.
    :param token: The API access token for the cloudcix API.
    """

    # Project Information
    # getting the list of all projects from the given region
    params = {'search[closed]': False}
    response = api.IAAS.project.list(token=token, params=params)
    if response.status_code != 200:
        print(
            f'HTTP Error {response.status_code} occurred while trying to list instances of IAAS.project.',
            f'\nResponse from api: {response.content.decode()}',
        )
        exit(1)
    projects = response.json()['content']
    if len(projects) == 0:
        print(f'\033[91m No Projects found in region #{region} \033[0m')
    else:
        # listing the projects
        label = f'Projects in region #{region}'
        print('┌─────────────────────────────────────────────────────────────┐')
        print(f'│{label:^61}│')
        print('├────────┬─────────────────────────────────────────┬──────────┤')
        print('│   ID   │                  Name                   │ Customer │')
        print('├────────┼─────────────────────────────────────────┼──────────┤')
        for project in projects:
            print(f'│{project["id"]:^8}│{project["name"]:^41}│{project["address_id"]:^10}│')
        print('└────────┴─────────────────────────────────────────┴──────────┘')
    return len(projects)


if __name__ == '__main__':
    os.system('clear')

    password = ''
    while password == '':
        password = getpass.getpass('[validator] Provide network password (exit quits); ')
    if password == 'exit':
        sys.exit()
    region_validator(password)
