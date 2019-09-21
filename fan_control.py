#!/usr/bin/env python3

import configparser
import getopt
import os
import re
import sensors # https://github.com/bastienleonard/pysensors.git
import subprocess
import sys
import time

config = {
    'debug': False,
    'config_path': '/opt/fan_control/fan_control.conf',
    'interval': 60,
    'thresholds': [
        {
            'temperature': 34,
            'fan_speed': 9
        }, {
            'temperature': 37,
            'fan_speed': 10
        }, {
            'temperature': 55,
            'fan_speed': 15
        }
    ]
}
state = {
    'fan_control_mode' : "automatic",
    'fan_speed': 0
}

def ipmitool(args):
    cmd = ["ipmitool"]
    cmd += (args.split(' '))
    if config['debug']:
        print(' '.join(cmd))
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

def set_fan_control(wanted_mode):
    global state

    if wanted_mode == "manual" or wanted_mode == "automatic":

        if wanted_mode == "manual" and state['fan_control_mode'] == "automatic":
            if not config['debug']:
                print("Switching to manual mode")
            ipmitool("raw 0x30 0x30 0x01 0x00")
        elif wanted_mode == "automatic" and state['fan_control_mode'] == "manual":
            if not config['debug']:
                print("Switching to automatic mode")
            ipmitool("raw 0x30 0x30 0x01 0x01")
            state['fan_speed'] = 0

        state['fan_control_mode'] = wanted_mode

def set_fan_speed(wanted_percentage):
    global state

    if wanted_percentage == state['fan_speed']:
        return

    if 5 <= wanted_percentage <= 100:
        wanted_percentage_hex = "{0:#0{1}x}".format(wanted_percentage, 4)
        if state['fan_control_mode'] != "manual":
            set_fan_control("manual")
            time.sleep(1)
        if not config['debug']:
            print("Setting fans speed to {}%".format(wanted_percentage))
        ipmitool("raw 0x30 0x30 0x02 0xff {}".format(wanted_percentage_hex))
        state['fan_speed'] = wanted_percentage

def parse_config():
    if not os.path.isfile(config['config_path']):
        print("Missing or unspecified configuration file, using defaults.")
    else:
        print("Loading custom configuration file.")
        parser = configparser.ConfigParser()
        parser.read(config['config_path'])
        for section in parser.sections():
            if section == 'Debug':
                config['debug'] = parser.getboolean(section, 'Enabled')
            elif section == 'Interval':
                config['interval'] = parser.getint(section, 'Seconds')
            elif re.match('^Threshold[123]$', section):
                i = int(section[-1]) - 1
                config['thresholds'][i]['temperature'] = parser.getint(section, 'Temperature')
                config['thresholds'][i]['fan_speed'] = parser.getint(section, 'FanSpeed')

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
            config['debug'] = True
        elif opt in ('-c', '--config'):
            config['config_path'] = arg
        elif opt in ('-i', '--interval'):
            config['interval'] = arg

def main():
    global state

    print("Starting fan control script with thresholds of {}°C ({}%), {}°C ({}%) and {}°C ({}%)".format(
            config['thresholds'][0]['temperature'], config['thresholds'][0]['fan_speed'],
            config['thresholds'][1]['temperature'], config['thresholds'][1]['fan_speed'],
            config['thresholds'][2]['temperature'], config['thresholds'][2]['fan_speed'],
        ))

    while True:
        temps = []
        cores = []

        for sensor in sensors.get_detected_chips():
            if sensor.prefix == "coretemp":
                cores.append(sensor)

        for core in cores:
            for feature in core.get_features():
                for subfeature in core.get_all_subfeatures(feature):
                    if subfeature.name.endswith("_input"):
                        temps.append(core.get_value(subfeature.number))

        temp_average = round(sum(temps)/len(temps))
        if config['debug']:
            print("T:{}°C M:{} S:{}%".format(temp_average, state['fan_control_mode'], state['fan_speed']))

        if temp_average <= config['thresholds'][0]['temperature']:
            set_fan_speed(config['thresholds'][0]['fan_speed'])
        elif config['thresholds'][0]['temperature'] < temp_average <= config['thresholds'][1]['temperature']:
            set_fan_speed(config['thresholds'][1]['fan_speed'])
        elif config['thresholds'][1]['temperature'] < temp_average <= config['thresholds'][2]['temperature']:
            set_fan_speed(config['thresholds'][2]['fan_speed'])
        elif config['thresholds'][2]['temperature'] < temp_average:
            set_fan_control("automatic")

        time.sleep(config['interval'])

if __name__ == "__main__":
    try:
        try:
            parse_opts()
        except (getopt.GetoptError, InterruptedError):
            sys.exit(1)
        parse_config()
        main()
    finally:
        sensors.cleanup()
