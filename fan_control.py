#!/usr/bin/env python3

import yaml
import getopt
import os
import re
import sensors # https://github.com/bastienleonard/pysensors.git
import subprocess
import sys
import time
import signal

config = {
    'config_path': '/opt/fan_control/fan_control.yaml',
    'general': {
        'debug': False,
        'interval': 60
    },
    'hosts': []
}
state = {}

class ConfigError(Exception):
    pass

def ipmitool(args, host):
    global state

    cmd = ["ipmitool"]
    if state[host['name']]['is_remote']:
        cmd += ['-I', 'lanplus']
        cmd += ['-H', host['remote_ipmi_credentials']['host']]
        cmd += ['-U', host['remote_ipmi_credentials']['username']]
        cmd += ['-P', host['remote_ipmi_credentials']['password']]
    cmd += (args.split(' '))
    if config['general']['debug']:
        print(re.sub(r'-([UP]) (\S+)', r'-\1 ___', ' '.join(cmd))) # Do not log IPMI credentials
        return True

    try:
        subprocess.check_output(cmd, timeout=15)
    except subprocess.CalledProcessError:
        print("\"{}\" command has returned a non-0 exit code".format(cmd), file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("\"{}\" command has timed out".format(cmd), file=sys.stderr)
        return False
    return True

def set_fan_control(wanted_mode, host):
    global state

    if wanted_mode == "manual" or wanted_mode == "automatic":
        if wanted_mode == "manual" and state[host['name']]['fan_control_mode'] == "automatic":
            if not config['general']['debug']:
                print("[{}] Switching to manual mode".format(host['name']))
            ipmitool("raw 0x30 0x30 0x01 0x00", host)
        elif wanted_mode == "automatic" and state[host['name']]['fan_control_mode'] == "manual":
            if not config['general']['debug']:
                print("[{}] Switching to automatic mode".format(host['name']))
            ipmitool("raw 0x30 0x30 0x01 0x01", host)
            state[host['name']]['fan_speed'] = 0

        state[host['name']]['fan_control_mode'] = wanted_mode

def set_fan_speed(threshold_n, host):
    global state

    wanted_percentage = host['speeds'][threshold_n]
    if wanted_percentage == state[host['name']]['fan_speed']:
        return

    if 5 <= wanted_percentage <= 100:
        wanted_percentage_hex = "{0:#0{1}x}".format(wanted_percentage, 4)
        if state[host['name']]['fan_control_mode'] != "manual":
            set_fan_control("manual", host)
            time.sleep(1)
        if not config['general']['debug']:
            print("[{}] Setting fans speed to {}%".format(host['name'], wanted_percentage))
        ipmitool("raw 0x30 0x30 0x02 0xff {}".format(wanted_percentage_hex), host)
        state[host['name']]['fan_speed'] = wanted_percentage

def parse_config():
    global config
    _debug = config['general']['debug']
    _interval = config['general']['interval']

    if not os.path.isfile(config['config_path']):
        raise RuntimeError("Missing or unspecified configuration file.")
    else:
        print("Loading configuration file.")
        _config = None
        try:
            with open(config['config_path'], 'r') as yaml_conf:
                _config = yaml.safe_load(yaml_conf)
        except yaml.YAMLError as err:
            raise err # TODO: pretty print
        config = _config
        if 'debug' not in list(config['general'].keys()):
            config['general']['debug'] = _debug
        if 'interval' not in list(config['general'].keys()):
            config['general']['interval'] = _interval

        for host in config['hosts']:
            if 'hysteresis' not in list(host.keys()):
                host['hysteresis'] = 0
            if len(host['temperatures']) != 3:
                raise ConfigError('Host "{}" has {} temperature thresholds instead of 3.'.format(host['name'], len(host['temperatures'])))
            if len(host['speeds']) != 3:
                raise ConfigError('Host "{}" has {} fan speeds instead of 3.'.format(host['name'], len(host['speeds'])))
            if ('remote_temperature_command' in list(host.keys()) or 'remote_ipmi_credentials' in list(host.keys()))  and \
                ('remote_temperature_command' not in list(host.keys()) or 'remote_ipmi_credentials' not in list(host.keys())):
                raise ConfigError('Host "{}" must specify either none or both "remote_temperature_command" and "remote_ipmi_credentials" keys.'.format(host['name']))
            if 'remote_ipmi_credentials' in list(host.keys()) and \
                ('host' not in list(host['remote_ipmi_credentials'].keys()) or \
                'username' not in list(host['remote_ipmi_credentials'].keys()) or \
                'password' not in list(host['remote_ipmi_credentials'].keys())):
                raise ConfigError('Host "{}" must specify either none or all "host", "username" and "password" values for the "remote_ipmi_credentials" key.'.format(host['name']))
            # TODO: check presence/validity of values instead of keys presence only

            if host['name'] in list(state.keys()):
                raise ConfigError('Duplicate "{}" host name found.'.format(host['name']))
            state[host['name']] = {
                'is_remote': 'remote_temperature_command' in list(host.keys()),
                'fan_control_mode': 'automatic',
                'fan_speed': 0
            }

def parse_opts():
    global config
    help_str = "fan_control.py [-d] [-c <path_to_config>] [-i <interval>]"

    try:
        opts, _ = getopt.getopt(sys.argv[1:],"hdc:i:",["help","debug","config=","interval="])
    except getopt.GetoptError as e:
      print("Unrecognized option. Usage:\n{}".format(help_str))
      raise getopt.GetoptError(e)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print(help_str)
            raise InterruptedError
        elif opt in ('-d', '--debug'):
            config['general']['debug'] = True
        elif opt in ('-c', '--config'):
            config['config_path'] = arg
        elif opt in ('-i', '--interval'):
            config['general']['interval'] = arg

def checkHysteresis(temperature, threshold_n, host):
    global state

    # Skip checks if hysteresis is disabled for this host
    if not host['hysteresis']:
        return True

    # Fan speed is higher than it should be or automatic mode is currently enabled
    if (state[host['name']]['fan_speed'] > host['speeds'][threshold_n] or
            state[host['name']]['fan_control_mode'] == 'automatic'):
        # T ≤ (threshold - hysteresis)
        return temperature <= host['temperatures'][threshold_n] - host['hysteresis']

    # Fan speed is lower than it should be, step up immediately and ignore hysteresis
    return True

def compute_fan_speed(temp_average, host):
    global state

    if config['general']['debug']:
        print("[{}] T:{}°C M:{} S:{}%".format(host['name'], temp_average, state[host['name']]['fan_control_mode'], state[host['name']]['fan_speed']))

    # Tavg < Threshold0
    if (
        temp_average <= host['temperatures'][0] and
        checkHysteresis(temp_average, 0, host)
    ):
        set_fan_speed(0, host)

    # Threshold0 < Tavg ≤ Threshold1
    elif (
        host['temperatures'][0] < temp_average <= host['temperatures'][1] and
        checkHysteresis(temp_average, 1, host)
    ):
        set_fan_speed(1, host)

    # Threshold1 < Tavg ≤ Threshold2
    elif (
        host['temperatures'][1] < temp_average <= host['temperatures'][2] and
        checkHysteresis(temp_average, 2, host)
    ):
        set_fan_speed(2, host)

    # Tavg > Threshold2
    elif host['temperatures'][2] < temp_average:
        set_fan_control("automatic", host)

def main():
    global config
    global state

    print("Starting fan control script.")
    for host in config['hosts']:
        print("[{}] Thresholds of {}°C ({}%), {}°C ({}%) and {}°C ({}%)".format(
                host['name'],
                host['temperatures'][0], host['speeds'][0],
                host['temperatures'][1], host['speeds'][1],
                host['temperatures'][2], host['speeds'][2],
            ))

    while True:
        for host in config['hosts']:
            temps = []

            if not state[host['name']]['is_remote']:
                cores = []
                for sensor in sensors.get_detected_chips():
                    if sensor.prefix == "coretemp":
                        cores.append(sensor)
                for core in cores:
                    for feature in core.get_features():
                        for subfeature in core.get_all_subfeatures(feature):
                            if subfeature.name.endswith("_input"):
                                temps.append(core.get_value(subfeature.number))
            else:
                cmd = os.popen(host['remote_temperature_command'])
                temps = list(map(lambda n: float(n), cmd.read().strip().split('\n')))
                cmd.close()

            temp_average = round(sum(temps)/len(temps))
            compute_fan_speed(temp_average, host)

        time.sleep(config['general']['interval'])


def graceful_shutdown(signalnum, frame):
    print("Signal {} received, giving up control".format(signalnum))
    for host in config['hosts']:
        set_fan_control("automatic", host)
    sys.exit(0)


if __name__ == "__main__":
    # Reset fan control to automatic when getting killed
    signal.signal(signal.SIGTERM, graceful_shutdown)

    try:
        try:
            parse_opts()
        except (getopt.GetoptError, InterruptedError):
            sys.exit(1)
        parse_config()
        main()
    finally:
        sensors.cleanup()
