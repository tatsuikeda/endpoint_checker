#!/usr/bin/env python3

import os
import json
import socket
import requests
import sys
from typing import Dict, List, Tuple
import dns.resolver
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from collections import defaultdict

def load_config():
    load_dotenv()
    endpoints = os.getenv('ENDPOINTS')
    dns_servers = os.getenv('DNS_SERVERS')
    return json.loads(endpoints), json.loads(dns_servers)

def select_dns_server():
    _, dns_servers = load_config()
    
    print("\nAvailable DNS Servers:")
    for i, (name, servers) in enumerate(dns_servers.items(), 1):
        print(f"{i}. {name} ({', '.join(servers)})")
    print("6. Check with all DNS providers")
    
    # Check if choice was provided as command line argument
    if len(sys.argv) > 1:
        try:
            choice = int(sys.argv[1])
        except ValueError:
            choice = 6  # Default to all providers if invalid input
    else:
        while True:
            try:
                choice = int(input("\nSelect DNS server (1-6): "))
                if 1 <= choice <= 6:
                    break
                print("Invalid choice. Please select a number between 1 and 6.")
            except ValueError:
                print("Please enter a valid number.")
    
    if 1 <= choice <= len(dns_servers):
        selected_name = list(dns_servers.keys())[choice-1]
        return [(selected_name, dns_servers[selected_name])]
    return list(dns_servers.items())  # Return all providers for option 6 or invalid input

def check_dns(endpoint: str, dns_servers: List[str]) -> dict:
    try:
        # Skip DNS resolution for IP addresses
        if endpoint[0].isdigit():
            return {'status': 'success', 'message': 'IP address', 'ip': endpoint}
        
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [socket.gethostbyname(server) if not server[0].isdigit() else server 
                              for server in dns_servers]
        
        answers = resolver.resolve(endpoint, 'A')
        ips = [str(rdata) for rdata in answers]
        return {'status': 'success', 'message': 'resolved', 'ip': ips}
    except Exception as e:
        return {'status': 'failed', 'message': str(e), 'ip': None}

def check_connection(endpoint: str, dns_info: Tuple[str, List[str]]) -> dict:
    dns_name, dns_servers = dns_info
    result = {
        'endpoint': endpoint,
        'dns_provider': dns_name,
        'dns': check_dns(endpoint, dns_servers)
    }
    
    try:
        # Try HTTPS first
        url = f'https://{endpoint}'
        response = requests.get(url, timeout=5, verify=True)
        result['https'] = {'status': 'success', 'code': response.status_code}
    except requests.exceptions.SSLError:
        result['https'] = {'status': 'failed', 'error': 'SSL Error'}
    except requests.exceptions.RequestException as e:
        result['https'] = {'status': 'failed', 'error': str(e)}
    
    try:
        # Try HTTP as fallback
        url = f'http://{endpoint}'
        response = requests.get(url, timeout=5)
        result['http'] = {'status': 'success', 'code': response.status_code}
    except requests.exceptions.RequestException as e:
        result['http'] = {'status': 'failed', 'error': str(e)}
    
    return result

def format_results(all_results: List[dict]) -> None:
    # Group results by endpoint
    endpoints_results = defaultdict(list)
    for result in all_results:
        endpoints_results[result['endpoint']].append(result)
    
    # Print results for each endpoint
    for endpoint, results in endpoints_results.items():
        print(f"\nEndpoint: {endpoint}")
        print("=" * 80)
        
        for result in results:
            dns_provider = result['dns_provider']
            dns_status = result['dns']
            https_status = result['https']
            http_status = result['http']
            
            print(f"\nDNS Provider: {dns_provider}")
            print(f"├─ DNS Resolution: {'✓' if dns_status['status'] == 'success' else '✗'} ({dns_status['message']})")
            if dns_status['ip']:
                print(f"├─ IP Address(es): {', '.join(dns_status['ip']) if isinstance(dns_status['ip'], list) else dns_status['ip']}")
            
            https_symbol = '✓' if https_status.get('status') == 'success' else '✗'
            https_info = f"Code: {https_status.get('code')}" if https_status.get('status') == 'success' else f"Error: {https_status.get('error')}"
            print(f"├─ HTTPS: {https_symbol} ({https_info})")
            
            http_symbol = '✓' if http_status.get('status') == 'success' else '✗'
            http_info = f"Code: {http_status.get('code')}" if http_status.get('status') == 'success' else f"Error: {http_status.get('error')}"
            print(f"└─ HTTP: {http_symbol} ({http_info})")
        
        print("-" * 80)

def main():
    print(f"Starting endpoint checks at {datetime.now()}")
    print("-" * 80)
    
    dns_providers = select_dns_server()
    endpoints, _ = load_config()
    
    all_results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for dns_info in dns_providers:
            results = list(executor.map(
                lambda endpoint: check_connection(endpoint, dns_info),
                endpoints
            ))
            all_results.extend(results)
    
    format_results(all_results)

if __name__ == "__main__":
    main()
