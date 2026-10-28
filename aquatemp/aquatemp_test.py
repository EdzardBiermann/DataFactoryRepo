#!/usr/bin/env python3
"""Test access to an Aqua Temp pool heat pump through the Linked-Go cloud.

Uses the same cloud API as the Aqua Temp phone app. By default it is read-only:
it logs in, lists your heat pumps and prints their current status.

    python aquatemp_test.py                 # list devices + status
    python aquatemp_test.py --power on      # switch on, then read back
    python aquatemp_test.py --power off --device <deviceCode>

Credentials, first found wins: env vars AQUATEMP_USER / AQUATEMP_PASS, the
.env file next to this script (copy .env.example), otherwise you are prompted.
"""

import argparse
import getpass
import hashlib
import json
import os
import sys
import time

import requests

# Newer accounts use the :449 crmservice API with an MD5 password; older
# accounts use cloudservice with the plain password. We try both.
API_VARIANTS = [
    {"base": "https://cloud.linked-go.com:449/crmservice/api", "md5": True, "user_field": "userName"},
    {"base": "https://cloud.linked-go.com:449/crmservice/api", "md5": True, "user_field": "user_name"},
    {"base": "https://cloud.linked-go.com/cloudservice/api", "md5": False, "user_field": "user_name"},
]

# Product IDs used by the community integrations when asking for the device list.
PRODUCT_IDS = [
    "1132174963097280512",
    "1186904563333062656",
    "1158905952238313472",
    "1245226668902080512",
    "1442284873216843776",
    "1548963836789501952",
]

STATUS_CODES = {
    "Power": "Power (1=on, 0=off)",
    "Mode": "Mode (0=cool, 1=heat, 2=auto)",
    "T02": "Water inlet temp (C)",
    "T03": "Water outlet temp (C)",
    "T05": "Ambient temp (C)",
    "R02": "Heating setpoint (C)",
}

VERBOSE = False


def log_raw(label, data):
    if VERBOSE:
        print(f"--- {label} ---")
        print(json.dumps(data, indent=2, ensure_ascii=False))


class AquaTemp:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json; charset=utf-8"
        self.base = None

    def post(self, path, payload):
        resp = self.session.post(self.base + path, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        log_raw(path, data)
        return data

    def login(self, user, password):
        for variant in API_VARIANTS:
            self.base = variant["base"]
            pw = hashlib.md5(password.encode()).hexdigest() if variant["md5"] else password
            payload = {variant["user_field"]: user, "password": pw, "type": "2"}
            try:
                data = self.post("/app/user/login", payload)
            except (requests.RequestException, ValueError) as exc:
                print(f"  {self.base} ({variant['user_field']}): {exc}")
                continue
            token = (data.get("objectResult") or {}).get("x-token")
            if str(data.get("error_code")) == "0" and token:
                self.session.headers["x-token"] = token
                print(f"Login OK via {self.base} ({variant['user_field']})")
                return
            print(f"  {self.base} ({variant['user_field']}): "
                  f"error_code={data.get('error_code')} {data.get('error_msg')}")
        sys.exit("Login failed with every API variant. Check e-mail/password "
                 "(same as the Aqua Temp app) and rerun with --verbose.")

    def devices(self):
        found = {}
        for path, payload in [
            ("/app/device/deviceList", {"productIds": PRODUCT_IDS}),
            ("/app/device/deviceList", {}),
            ("/app/device/getMyAppectDeviceShareDataList", {"productIds": PRODUCT_IDS}),
        ]:
            try:
                data = self.post(path, payload)
            except (requests.RequestException, ValueError) as exc:
                print(f"  {path}: {exc}")
                continue
            for dev in data.get("objectResult") or []:
                if isinstance(dev, dict) and dev.get("deviceCode"):
                    found[dev["deviceCode"]] = dev
        return list(found.values())

    def status(self, device_code):
        data = self.post("/app/device/getDataByCode",
                         {"deviceCode": device_code, "protocalCodes": list(STATUS_CODES)})
        return {item.get("code"): item.get("value") for item in data.get("objectResult") or []}

    def set_power(self, device_code, on):
        data = self.post("/app/device/control", {"param": [
            {"deviceCode": device_code, "protocolCode": "Power", "value": "1" if on else "0"}]})
        if str(data.get("error_code")) != "0":
            sys.exit(f"Control failed: error_code={data.get('error_code')} {data.get('error_msg')}")


def print_status(api, dev):
    code = dev["deviceCode"]
    name = dev.get("deviceNickName") or dev.get("deviceName") or "?"
    print(f"\nDevice {name}  code={code}  status={dev.get('deviceStatus', '?')}  "
          f"product={dev.get('productId', '?')}")
    try:
        values = api.status(code)
    except (requests.RequestException, ValueError) as exc:
        print(f"  status read failed: {exc}")
        return None
    for key, label in STATUS_CODES.items():
        print(f"  {label:32} {values.get(key, '-')}")
    return values


def load_config():
    """Read KEY=VALUE lines from the .env file next to this script, if present."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    config = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip().strip("\"'")
    return config


def main():
    global VERBOSE
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--power", choices=["on", "off"], help="switch the heat pump on or off")
    parser.add_argument("--device", help="deviceCode to control (default: the only/first device)")
    parser.add_argument("--verbose", action="store_true", help="print raw API responses")
    args = parser.parse_args()
    VERBOSE = args.verbose
    # The cloud returns some error messages in Chinese; don't crash on a cp1252 console.
    sys.stdout.reconfigure(errors="replace")

    config = load_config()
    user = (os.environ.get("AQUATEMP_USER") or config.get("AQUATEMP_USER")
            or input("Aqua Temp e-mail: ").strip())
    password = (os.environ.get("AQUATEMP_PASS") or config.get("AQUATEMP_PASS")
                or getpass.getpass("Aqua Temp password: "))

    api = AquaTemp()
    api.login(user, password)

    devices = api.devices()
    if not devices:
        sys.exit("Logged in, but no devices found. Rerun with --verbose and share the output.")
    print(f"Found {len(devices)} device(s)")
    for dev in devices:
        print_status(api, dev)

    if args.power:
        target = next((d for d in devices if d["deviceCode"] == args.device), None) if args.device else devices[0]
        if not target:
            sys.exit(f"Device {args.device} not found")
        print(f"\nSwitching {target['deviceCode']} {args.power.upper()} ...")
        api.set_power(target["deviceCode"], args.power == "on")
        time.sleep(5)
        values = print_status(api, target)
        expected = "1" if args.power == "on" else "0"
        if values and str(values.get("Power")) == expected:
            print(f"\nOK: heat pump reports power {args.power.upper()}")
        else:
            print("\nCommand sent, but read-back does not match yet; check the app.")


if __name__ == "__main__":
    main()
