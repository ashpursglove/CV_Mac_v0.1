#!/usr/bin/env python3
"""
list_usb_devices.py

Query macOS for USB devices via `system_profiler`, parse the JSON output,
and print a friendly, indented list of every device and its key properties.
"""

import subprocess
import json
import sys

# Which fields to show (if present)
DESIRED_FIELDS = [
    ('manufacturer', 'Manufacturer'),
    ('vendor_id',    'Vendor ID'),
    ('product_id',   'Product ID'),
    ('serial_num',   'Serial Number'),
    ('location_id',  'Location ID'),
    ('version',      'Version'),
    ('speed',        'Speed'),
    ('bus_power',    'Bus Power'),
    ('current_available', 'Current Available'),
    ('built_in',     'Built-In'),
]

def get_usb_json():
    """Run system_profiler to get SPUSBDataType as JSON."""
    try:
        proc = subprocess.run(
            ["system_profiler", "SPUSBDataType", "-json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        print("Error running system_profiler:", e.stderr.strip(), file=sys.stderr)
        sys.exit(1)
    return json.loads(proc.stdout)

def flatten_devices(items, depth=0, out=None):
    """
    Recursively walk a list of items from system_profiler JSON,
    collecting each device node into `out` along with its depth.
    """
    if out is None:
        out = []
    for dev in items:
        out.append((depth, dev))
        # child devices live in '_items'
        for child_list_key in ['_items', 'usb_children']:
            if child_list_key in dev:
                flatten_devices(dev[child_list_key], depth+1, out)
    return out

def print_devices(flat_list):
    """Print each device in order, with indentation and desired fields."""
    for depth, dev in flat_list:
        indent = "  " * depth
        name = dev.get('_name') or dev.get('name') or "<Unknown Device>"
        print(f"{indent}• {name}")
        for key, label in DESIRED_FIELDS:
            if key in dev:
                print(f"{indent}    {label}: {dev[key]}")
        print()  # blank line between devices

def main():
    data = get_usb_json()
    # system_profiler nests USB info under SPUSBDataType → list
    usb_list = data.get('SPUSBDataType', [])
    if not usb_list:
        print("No USB data found.", file=sys.stderr)
        sys.exit(1)

    flat = flatten_devices(usb_list)
    print("\nDetected USB devices:\n")
    print_devices(flat)

if __name__ == "__main__":
    main()
