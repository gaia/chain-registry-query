#!/usr/bin/env python3
import requests
import telnetlib
from ping3 import ping, verbose_ping
import argparse
import json
import sys
import os
from prettytable import PrettyTable

banner = """
         _____ ______  _____
        /  __ \| ___ \|  _  |
        | /  \/| |_/ /| | | |
        | |    |    / | | | |
        | \__/\| |\ \ \ \/' /
         \____/\_| \_| \_/\_\

       Chain Registry Query Tool
    v0.1.0 | Author: github.com/gaia
"""
print(banner)

# Parse the command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument("chain", help="the name of the chain")
parser.add_argument("type", help="the type of peers (seeds, persistent_peers, rpc, rest, grpc)")
parser.add_argument("--max_results", type=int, help="the maximum number of results to display (still tests all results)")
parser.add_argument("--polkachu", action="store_true", help="use the polkachu API instead of the registry (alternate source of persistent peers)")
parser.add_argument("--no_fileout", action="store_true", help="do not create a file with successful seeds and persistent_peers results (ready to paste in config.toml)")
args = parser.parse_args()
if args.polkachu and args.type != "persistent_peers":
    print("Error: Only 'persistent_peers' is valid with the --polkachu parameter.")
    exit(1)
if args.type not in ["persistent_peers", "seeds", "rpc", "rest", "grpc"]:
    print("Error: Resource type must be either persistent_peers, seeds, rpc, rest or grpc.")
    exit(1)

# Function to check internet connection
def check_internet_connectivity():
    response = os.system("ping -c 1 1.1.1.1 > /dev/null 2>&1")
    if response != 0:
        print("Error: No internet connection")
        sys.exit(1)

check_internet_connectivity()

# Function to perform a ping test
def ping_test(address):
    return ping(address, timeout=0.5) or 0
# Function to perform a telnet test
def telnet_test(address, port):
    # TODO: A more use case specific test routine for seeds, persistent_peers, rest and grpc. Already implemented for rpc.
    try:
        with telnetlib.Telnet(address, port, timeout=0.5) as connection:
            return True
    except:
        return False

def print_out_peers(successful_entries, failed_entries):
    print(f"\r\n\n========== SEEDS and PERSISTENT PEERS are tested via telnet then ping.")
    # Sort the successful entries by ping time
    successful_entries.sort(key=lambda x: x[3])
    # If max_results is provided, only display the top max_results entries
    if args.max_results is not None:
        successful_entries = successful_entries[:args.max_results]
    # Print the successful entries in table format
    table_success = PrettyTable()
    table_success.field_names = ["NODE-ID", "ADDRESS:PORT", "PING TIME (ms)"]
    for node_id, address, port, ping_time in successful_entries:
        table_success.add_row([node_id, f"{address}:{port}", ping_time])
    print("\r\nSuccess ======================================================================================\r\n Ping reply time 0 means the server did not reply to the ping.\r\n You might want to manually traceroute these servers to find the closest.")
    print(table_success)
    # Print the failed entries in table format
    table_failed = PrettyTable()
    table_failed.field_names = ["NODE-ID", "ADDRESS:PORT", "REASON"]
    for node_id, address, port, reason in failed_entries:
        table_failed.add_row([node_id, f"{address}:{port}", reason])
    print("\nFailed =======================================================================================")
    print(table_failed)
    # Write the successful entries to a file
    if not args.no_fileout:
        output_file = (f"{args.chain}-{args.type}-filtered.txt")
        print(f"\r\nWriting out ready-to-paste results to {output_file}")
        with open(f"{output_file}", "w") as f:
            f.write(",".join([f"{node_id}@{address}:{port}" for node_id, address, port, ping_time in successful_entries]))

def print_out_apis(successful_entries, failed_entries):
    print(f"\r\n\n========== GRPC and REST servers are tested via telnet then ping.")
    # Sort the successful entries by ping time
    successful_entries.sort(key=lambda x: x[2])
    # If max_results is provided, only display the top max_results entries
    if args.max_results is not None:
        successful_entries = successful_entries[:args.max_results]
    # Print the successful entries in table format
    table_success = PrettyTable()
    table_success.field_names = ["ADDRESS:PORT", "PING TIME (ms)"]
    for address, port, ping_time in successful_entries:
        table_success.add_row([f"{address}:{port}", ping_time])
    print("\r\nSuccess ======================================================================================\r\n Ping reply time 0 means the server did not reply to the ping.\r\n You might want to manually traceroute these servers to find the closest.")
    print(table_success)
    # Print the failed entries in table format
    table_failed = PrettyTable()
    table_failed.field_names = ["ADDRESS:PORT", "REASON"]
    for address, port, reason in failed_entries:
        table_failed.add_row([f"{address}:{port}", reason])
    print("\nFailed =======================================================================================")
    print(table_failed)
    # No file output for APIs

def print_out_apis_rpc(successful_entries, failed_entries):
    print(f"\r\n\n========== RPC servers are tested via curl then ping /status.")
    # address, port, ping_time, tx_index, catching_up
    # Sort the successful entries by ping time
    successful_entries.sort(key=lambda x: x[2])
    # If max_results is provided, only display the top max_results entries
    if args.max_results is not None:
        successful_entries = successful_entries[:args.max_results]
    # Print the successful entries in table format
    table_success = PrettyTable()
    table_success.field_names = ["ADDRESS:PORT", "PING TIME (ms)", "TX INDEXING", "CATCHING UP", "VOTING POWER"]
    for address, port, ping_time, tx_index, catching_up, voting_power in successful_entries:
        table_success.add_row([f"{address}:{port}", ping_time, tx_index, catching_up, voting_power])
    print("\r\nSuccess ======================================================================================\r\n Ping reply time 0 means the server did not reply to the ping.\r\n You might want to manually traceroute these servers to find the closest.")
    print(table_success)
    # Print the failed entries in table format
    table_failed = PrettyTable()
    table_failed.field_names = ["ADDRESS:PORT", "REASON"]
    for address, port, reason in failed_entries:
        table_failed.add_row([f"{address}:{port}", reason])
    print("\nFailed =======================================================================================\r\n 'Error 200' means the server replied, but not as expected.")
    print(table_failed)
    # No file output for APIs

######################################
# List to store the successful entries
successful_entries = []
# Lists to store the successful and failed entries
failed_entries = []

if args.polkachu:
    # Define the API endpoint and headers
    url = f"https://polkachu.com/api/v1/chains/{args.chain}/live_peers"
    print(f"\r\nUsing {url}\r\n")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    # Make the API request
    response = requests.get(url, headers=headers)
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        # Perform the tests on each entry in the "live_peers" array
        for entry in data["live_peers"]:
            message = f"Testing {entry}"
            print(f"\r{message:160}", end="")
            sys.stdout.flush()
            # Extract the NODE-ID, ADDRESS, and PORT
            node_id, address_port = entry.split("@")
            address, port = address_port.split(":")
            # Perform the tests
            telnet_success = telnet_test(address, port)
            ping_time = ping_test(address)
            # If the telnet test was successful, add the entry to the list
            if telnet_success:
                successful_entries.append((node_id, address, port, round(ping_time * 1000, 2)))
            else:
                failed_entries.append((node_id, address, port, "Telnet"))
        print_out_peers(successful_entries, failed_entries)

else:
    # Define the URL
    url = f"https://raw.githubusercontent.com/cosmos/chain-registry/master/{args.chain}/chain.json"
    print(f"\r\nUsing {url}\r\n")
    # Make the request
    response = requests.get(url)
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = json.loads(response.text)
        # Extract the NODE-ID and ADDRESS:PORT
        if args.type in ["seeds", "persistent_peers"]:
            for peer in data["peers"][args.type]:
                message = f"Testing {peer}"
                print(f"\r{message:160}", end="")
                sys.stdout.flush()
                node_id = peer["id"]
                address_port = peer["address"]
                address, port = address_port.split(":")
                # Perform the tests
                telnet_success = telnet_test(address, port)
                ping_time = ping_test(address)
                # If the telnet test was successful, add the entry to the list
                if telnet_success:
                    successful_entries.append((node_id, address, port, round(ping_time * 1000, 2)))
                else:
                    failed_entries.append((node_id, address, port, "Telnet"))
            print_out_peers(successful_entries, failed_entries)
        elif args.type != "rpc":
            for api in data["apis"][args.type]:
                message = f"Testing {api['address']}"
                print(f"\r{message:160}", end="")
                sys.stdout.flush()
                if args.type == "grpc":
                    # grpc format: "example.com:11290"
                    address, port = api["address"].split(":")
                else:
                    # rpc and rest format: "https://example.com:443"
                    protocol, rest = api["address"].split("://")
                    if ":" in rest:
                        address, port = rest.split(":")
                    else:
                        address = rest
                        if protocol == "http":
                            port = "80"
                        elif protocol == "https":
                            port = "443"
                # Perform the tests
                telnet_success = telnet_test(address, port)
                ping_time = ping_test(address)
                # If the telnet test was successful, add the entry to the list
                if telnet_success:
                    successful_entries.append((address, port, round(ping_time * 1000, 2)))
                else:
                    failed_entries.append((address, port, "Telnet"))
            print_out_apis(successful_entries, failed_entries)
        else:
            # Query the RPC
            for api in data["apis"]["rpc"]:
                message = f"Testing {api['address']}"
                print(f"\r{message:160}", end="")
                sys.stdout.flush()
                # rpc and rest format: "https://example.com:443"
                protocol, rest = api["address"].split("://")
                if ":" in rest:
                    address, port = rest.split(":")
                else:
                    address = rest
                    if protocol == "http":
                        port = "80"
                    elif protocol == "https":
                        port = "443"
                # Perform the ping test
                ping_time = ping_test(address)
                # If the ping test was successful, perform the telnet test
                if ping_time is not None:
                    try:
                        rpc_response = requests.get(f"{protocol}://{address}:{port}/status")
                        rpc_data = rpc_response.json()
                        if rpc_response.status_code == 200:
                            #print(rpc_data)
                            tx_index = rpc_data['result']['node_info']['other']['tx_index']
                            catching_up = rpc_data['result']['sync_info']['catching_up']
                            voting_power = rpc_data['result']['validator_info']['voting_power']
                            successful_entries.append((address, port, round(ping_time * 1000, 2), tx_index, catching_up, voting_power))
                    except Exception as e:  # Handle JSON decoding error and other possible exceptions
                        failed_entries.append((address, port, f"Error {rpc_response.status_code}"))
                else:
                    failed_entries.append((address, port, "No response"))
            print_out_apis_rpc(successful_entries, failed_entries)
