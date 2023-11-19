#!/usr/bin/env python3
import requests
import telnetlib
from ping3 import ping, verbose_ping
import argparse
import json
import sys
import os
from prettytable import PrettyTable
import socket
import websockets
import asyncio
import re

banner = """
         _____ ______  _____
        /  __ \| ___ \|  _  |
        | /  \/| |_/ /| | | |
        | |    |    / | | | |
        | \__/\| |\ \ \ \/' /
         \____/\_| \_| \_/\_\

       Chain Registry Query Tool
    v0.1.2 | Author: github.com/gaia
"""
print(banner)

# Parse the command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument("chain", help="the name of the chain")
parser.add_argument("type", help="the type of resource to query (seeds, persistent_peers, rpc, rest, grpc)")
parser.add_argument("--max_results", type=int, help="the maximum number of results to display (still tests all results)")
parser.add_argument("--polkachu", action="store_true", help="use the polkachu API instead of the registry (alternate source of persistent peers)")
parser.add_argument("--fileout", action="store_true", help="do create a file with successful seeds and persistent_peers results (ready to paste in config.toml)")
parser.add_argument("--require-ws", action="store_true", help="Only show RPC results with WebSockets available")
args = parser.parse_args()
if args.polkachu and args.type != "persistent_peers":
    print("Error: Only 'persistent_peers' is valid with the --polkachu parameter.")
    exit(1)
if args.type not in ["persistent_peers", "seeds", "rpc", "rest", "grpc"]:
    print("Error: Resource type must be either persistent_peers, seeds, rpc, rest or grpc.")
    exit(1)

# Function to check internet connection
def check_internet_connectivity():
    response = os.system("ping -W 0.5 -c 1 1.1.1.1 > /dev/null 2>&1")
    if response != 0:
        print("Error: No internet connection")
        sys.exit(1)

check_internet_connectivity()

# Function to perform a ping test
def ping_test(address):
    try:
        return ping(address, timeout=0.5) or 0
    except socket.gaierror:
        print(f"Could not resolve {address}. Skipping...")
        raise
# Function to perform a telnet test
def telnet_test(address, port):
    # TODO: A more use case specific test routine for seeds, persistent_peers, rest and grpc. Already implemented for rpc.
    try:
        with telnetlib.Telnet(address, port, timeout=0.5) as connection:
            return True
    except socket.gaierror:
        print(f"Could not resolve {address}. Skipping...")
        raise
    except:
        return False

# Function to catch odd cases when the RPC has a path after the URI, e.g., akash-services.provider.com:443/rpc
def contains_only_numbers_or_slash(s):
    # Regular expression pattern: one or more digits, optionally followed by a slash
    s = s.rstrip('/')
    pattern = r'^\d+/?$'
    return bool(re.match(pattern, s))

# Function to perform a Websocket test
async def test_websocket(address, port):
    if contains_only_numbers_or_slash(port):
        port = int(port)
        uri = f"wss://{address}:{port}/websocket" if port == 443 else f"ws://{address}:{port}/websocket"
        try:
            async with websockets.connect(uri) as websocket:
                pong_waiter = await websocket.ping()
                try:
                    await asyncio.wait_for(pong_waiter, timeout=0.5)
                    return "Available"
                except asyncio.TimeoutError:
                    #print("Ping timeout")
                    return "N/A"
        except Exception as e:
            #print(f"Connection failed: {e}")
            return "N/A"
    else:
        return "N/A"

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
    if args.fileout:
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
   # Sort the successful entries by ping time
   successful_entries.sort(key=lambda x: x[2])
   # If require-ws is provided, only keep entries with WebSockets available
   if args.require_ws:
       successful_entries = [entry for entry in successful_entries if entry[-1] == "Available"]
    # If max_results is provided, only display the top max_results entries
   if args.max_results is not None:
       successful_entries = successful_entries[:args.max_results]
   # Print the successful entries in table format
   table_success = PrettyTable()
   table_success.field_names = ["ADDRESS:PORT", "PING TIME (ms)", "TX INDEXING", "CATCHING UP", "VOTING POWER", "WEBSOCKETS?"]
   for address, port, ping_time, tx_index, catching_up, voting_power, websocket_status in successful_entries:
       table_success.add_row([f"{address}:{port}", ping_time, tx_index, catching_up, voting_power, websocket_status])
   print("\r\nSuccess ======================================================================================\r\n Ping reply time 0 means the server did not reply to the ping.\r\n You might want to manually traceroute these servers to find the closest.")
   print(table_success)
   # Print the failed entries in table format
   table_failed = PrettyTable()
   table_failed.field_names = ["ADDRESS:PORT", "REASON"]
   for address, port, reason in failed_entries:
       table_failed.add_row([f"{address}:{port}", reason])
   print("\nFailed =======================================================================================\r\n 'Error 200' means the server replied, but not as expected or within the allowed timeframe.")
   print(table_failed)
   # No file output for APIs

######################################
# List to store the successful entries
successful_entries = []
# Lists to store the successful and failed entries
failed_entries = []

if args.polkachu:
    # Define the API endpoint and headers
    url = f"https://polkachu.com/api/v2/chains/{args.chain}/live_peers"
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
            try:
                telnet_success = telnet_test(address, port)
                ping_time = ping_test(address)
            except socket.gaierror:
                continue
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
    response = requests.get(url, timeout=0.5)
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
                try:
                    telnet_success = telnet_test(address, port)
                    ping_time = ping_test(address)
                except socket.gaierror:
                    continue
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
                        address = rest.rstrip('/')
                        if protocol == "http":
                            port = "80"
                        elif protocol == "https":
                            port = "443"
                # Perform the tests
                try:
                    telnet_success = telnet_test(address, port)
                    ping_time = ping_test(address)
                except socket.gaierror:
                    continue
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
                    if port.endswith('/'):
                        port = port.rstrip('/')
                    if port == "80" or port == "443":
                        address = address.rstrip('/')
                else:
                    address = rest.rstrip('/')
                    if protocol == "http":
                        port = "80"
                    elif protocol == "https":
                        port = "443"
                # Perform the RPC response test
                try:
                    # Two seconds timeout might seem like a lot but a lot of RPCs won't complete the operation in 1 second or less.
                    rpc_response = requests.get(f"{protocol}://{address}:{port}/status", timeout=2)
                    rpc_data = rpc_response.json()
                    if rpc_response.status_code == 200:
                        tx_index = rpc_data['result']['node_info']['other']['tx_index']
                        catching_up = rpc_data['result']['sync_info']['catching_up']
                        # Voting power is sometimes filtered out so an exception is added, assuming 0 when it can't be retrieved
                        if 'validator_info' in rpc_data['result'] and 'voting_power' in rpc_data['result']['validator_info']:
                            voting_power = rpc_data['result']['validator_info']['voting_power']
                        else:
                            voting_power = "0"
                    else:
                        failed_entries.append((address, port, f"Error {rpc_response.status_code}"))
                except Exception as e:  # Handle JSON decoding error and other possible exceptions
                    failed_entries.append((address, port, f"Error {rpc_response.status_code}"))
                # Perform the ping test
                ping_time = ping_test(address) or 0
                # Perform the WebSocket test
                websocket_status = asyncio.run(test_websocket(address, port))
                # Add the results to the successful_entries list
                successful_entries.append((address, port, round(ping_time * 1000, 2), tx_index, catching_up, voting_power, websocket_status))
            print_out_apis_rpc(successful_entries, failed_entries)

