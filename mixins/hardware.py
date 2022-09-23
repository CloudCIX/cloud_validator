# stdlib
import getpass
import os
import subprocess
import time
from collections import deque
from typing import Deque
# lib
from paramiko import AutoAddPolicy, Channel, SSHClient, SSHException


class HardwareMixin:
    """
    Mixin for providing access to ping the server.
    """

    def ping(self, type: str, id: str, ip: str, response: bool):
        """
        Ping the hardware.
        :param type: The hardware type being pinged e.g 'VM'. Used for printing messages.
        :param id: The ID number of the hardware being pinged.
        :param ip: The IP address of the hardware being pinged.
        :param response: True if receiving a response from the server is the successful scenario.
        """

        timeout = time.time() + 10 * 60
        loop_count = 0
        while time.time() < timeout:
            loop_count += 1
            print(f'\r - Trying to ping {type} #{id} at IP {ip}{"." * loop_count}', end='')
            ping = subprocess.Popen(['ping', '-c', '1', '-W', '1', str(ip)], stdout=subprocess.PIPE)
            if not ping.wait() and response:
                print(f'\r\033[92m - {type} #{id} is pingable at IP {ip}{" " * 100} \033[0m')
                return
            elif ping.wait() and not response:
                print(f'\r\033[92m - {type} #{id} is not pingable at IP {ip} \033[0m')
                return
            time.sleep(10)

        if response:
            print(f'\r\033[91m - {type} #{id} is not pingable at IP {ip}{" " * 100} \033[0m')
        else:
            print(f'\r\033[91m - {type} #{id} is still pingable at IP {ip} \033[0m')
        exit(1)

    def fetcher(self, data: dict):
        """
        This method is used to get the out put of a command from the unix based servers
        :param data: dict contains detials like user name, server ip, password, command
        :return: result: string contains out put of the command from server
        """
        result = {}
        client = SSHClient()
        client.set_missing_host_key_policy(AutoAddPolicy())
        try:
            client.connect(data['server_ip'], port=22, username=data['user_name'], password=data['password'])
            # Run the command via the client
            _, stdout, stderr = client.exec_command(data['command'])
            # Block until command finishes
            stdout.channel.recv_exit_status()
            # Read the full response from both channels
            output = self.get_full_response(stdout.channel)
            error = self.get_full_response(stderr.channel)
            if output:
                result['output'] = output
            if error:
                result['error'] = error
        except SSHException:
            print(f'Failed to connect the client server at {data["server_ip"]}')
        finally:
            client.close()
        return result

    def stress_test(self, public_ip: str, vm_id: int):
        """
        Test concurrent connections to the VM
        """
        print(' - Checking bandwidth of VM')
        success = self.prepare_for_test(public_ip, vm_id)
        if not success:
            print(f'\r\033[91m - VM #{vm_id} Could not be set up for bandwidth tests.\033[0m')
            return

        os.system('clear')
        print('Testing traffic')
        proc = subprocess.run(f'nping -c 3 -p 22,5353,80 {public_ip}', shell=True)
        if proc.returncode != 0:
            print(f'Failure pinging open ports for VM at {public_ip}')
        proc = subprocess.run(f'iperf3 -P 4 -c {public_ip}', shell=True)
        if proc.returncode != 0:
            print(f'Failure stressing traffic for VM at {public_ip}')

    def prepare_for_test(self, public_ip, vm_id):
        password = ''
        while password == '':
            password = getpass.getpass(f'[validator] Provide password for VM {vm_id} (exit quits): ')
        if password == 'exit':
            return False
        print('Password set')

        cmds = [
            f"echo '{password}' | sudo -S apt-get -y update",
            f"echo '{password}' | sudo -S apt-get -q install -y nginx dnsmasq iperf3",
            f"echo '{password}' | sudo -S nginx",
            f"echo '{password}' | sudo -S dnsmasq -p 5353",
            f"echo '{password}' | sudo -S iperf3 -s -D",
        ]

        # Get an ssh session to the VM
        success = True
        client = SSHClient()
        client.set_missing_host_key_policy(AutoAddPolicy())
        try:
            print(f'Connecting to host {public_ip}')
            client.connect(public_ip, username='administrator', password=password)

            for cmd in cmds:
                print(cmd)
                _, stdout, stderr = client.exec_command(cmd)
                # Block until command finishes
                stdout.channel.recv_exit_status()
                # Read any errors
                error = self.get_full_response(stderr.channel, wait_time=1)
                if error:
                    print(error)
        except SSHException:
            print('Failed to set up VM for bandwidth tests')
            success = False
        finally:
            client.close()
        return success

    @staticmethod
    def get_full_response(channel: Channel, wait_time: int = 15, read_size: int = 64) -> str:
        """
        Get the full response from the specified paramiko channel, waiting a given number of seconds before trying to
        read from it each time.
        :param channel: The channel to be read from
        :param wait_time: How long in seconds between each read
        :param read_size: How many bytes to be read from the channel each time
        :return: The full output from the channel, or as much as can be read given the parameters.
        """
        fragments: Deque[str] = deque()
        time.sleep(wait_time)
        while channel.recv_ready():
            fragments.append(channel.recv(read_size).decode())
            time.sleep(wait_time)
        return ''.join(fragments)
