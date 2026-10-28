# Aqua Temp access test

Step 1 of the solar automation. It checks that the heat pump can be read and
switched through the Aqua Temp (Linked-Go) cloud, which is the same backend the phone app uses.

## Run

Use any machine on the internet: a PC, a Raspberry Pi or the Home Assistant terminal.

```bash
pip install -r requirements.txt
python aquatemp_test.py                # log in, list heat pumps, show status (read-only)
python aquatemp_test.py --power on     # switch on and read back
python aquatemp_test.py --power off
```

On an Android phone, install **Termux** and then run:

```bash
pkg install python && pip install requests
python aquatemp_test.py
```

Use the same e-mail and password as the Aqua Temp app. The script takes them from, in order:

1. the `AQUATEMP_USER` / `AQUATEMP_PASS` environment variables,
2. a `.env` file next to the script: copy `.env.example` to `.env` and fill it in
   (`.env` is in `.gitignore`, so it is never pushed),
3. a prompt, if neither is set.

## Expected output

```
Login OK via https://cloud.linked-go.com:449/crmservice/api (userName)
Found 1 device(s)

Device Pool  code=XXXXXXXX  status=ONLINE  product=...
  Power (1=on, 0=off)              0
  Mode (0=cool, 1=heat, 2=auto)    1
  Water inlet temp (C)             24.5
  ...
```

If any step fails, rerun with `--verbose` and share the raw responses. Remove the token first.

## Home Assistant

[`../home-assistant/packages/pool_heat_pump.yaml`](../home-assistant/packages/pool_heat_pump.yaml)
uses the same API to give Home Assistant a `switch.pool_heat_pump` and temperature sensors.
