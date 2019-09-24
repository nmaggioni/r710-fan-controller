# Dell R710 Fan Control Script

> A temperature-based fan speed controller for Dell servers (tested on an R710, should work with most PowerEdges).


- [Dell R710 Fan Control Script](#dell-r710-fan-control-script)
  - [Requisites](#requisites)
  - [Installation / Upgrade](#installation--upgrade)
  - [Configuration](#configuration)
  - [How it works](#how-it-works)
  - [Credits](#credits)

---

## Requisites

1. Python 3 is installed.
2. **IPMI Over LAN** is enabled in iDRAC (_Login > Network/Security > IPMI Settings_).
3. `lm-sensors` is installed and configured.
   + Example output of `sensors` for a dual CPU system:
        ```text
        coretemp-isa-0000
        Adapter: ISA adapter
        Core 0:       +38.0°C  (high = +69.0°C, crit = +79.0°C)
        Core 1:       +46.0°C  (high = +69.0°C, crit = +79.0°C)
        Core 2:       +40.0°C  (high = +69.0°C, crit = +79.0°C)
        Core 8:       +43.0°C  (high = +69.0°C, crit = +79.0°C)
        Core 9:       +39.0°C  (high = +69.0°C, crit = +79.0°C)
        Core 10:      +39.0°C  (high = +69.0°C, crit = +79.0°C)

        coretemp-isa-0001
        Adapter: ISA adapter
        Core 0:       +29.0°C  (high = +69.0°C, crit = +79.0°C)
        Core 1:       +35.0°C  (high = +69.0°C, crit = +79.0°C)
        Core 2:       +29.0°C  (high = +69.0°C, crit = +79.0°C)
        Core 8:       +34.0°C  (high = +69.0°C, crit = +79.0°C)
        Core 9:       +33.0°C  (high = +69.0°C, crit = +79.0°C)
        Core 10:      +31.0°C  (high = +69.0°C, crit = +79.0°C)
        ```

## Installation / Upgrade

Clone the repo and run the installation script as root to configure the system or upgrade the already installed controller:

```text
git clone https://github.com/nmaggioni/r710-fan-controller.git
cd r710-fan-controller
sudo ./install.sh [<installation path>]
```

The default installation path is `/opt/fan_control` and the service will be installed as `fan-control.service`. If a configuration file already exists, it will be renamed with a `.old` extension.

## Configuration

You can tune the controller's settings via the `fan_control.conf` file in the installation directory.

| Section | Property | Default Value | Description |
| ------- | -------- | ------------- | ----------- |
| General | Debug | `false` | Toggle debug mode _(print ipmitools commands instead of executing them, additional logging)_. |
| General | Interval | 60 | How often (in seconds) to read the CPUs' temperatures and adjust the fans' speeds. |
| General | Hysteresis | 0 | How many degrees (in °C) the CPUs' temperature must go below the threshold to trigger slowing the fans down. Prevents rapid speed changes, a good starting value can be `3`. |
| Threshold{1,2,3} | Temperature | [32, 37, 55] | The upper bound (in °C) of this threshold, _see below for details._ |
| Threshold{1,2,3} | FanSpeed | [9, 10, 15] | The speed (in %) at which fans will run for this threshold, _see below for details._ |

## How it works

Every `Interval` the controller will get the temperatures of all the available CPU cores, average them and round the result (referred to as _Tavg_ below). It will then follow this logic to set the fans' speed percentage or engage automatic (hardware managed) control.

| Condition | Fan speed |
| --- | --- |
| _Tavg_ ≤ Threshold1 | Threshold1 |
| Threshold1 < _Tavg_ ≤ Threshold2 | Threshold2 |
| Threshold2 < _Tavg_ ≤ Threshold3 | Threshold3 |
| _Tavg_ > Threshold3 | Automatic |

If `Hysteresis` is set, the controller will wait for the temperature to go below _ThresholdN - Hysteresis_ temperature. For example: with a Threshold2 of 37°C and an hysteresis of 3°C, the fans won't slow down from Threshold3 to Threshold2 speed until the temperature reaches 34°C.

## Credits

Major thanks go to [NoLooseEnds's directions](https://github.com/NoLooseEnds/Scripts/tree/master/R710-IPMI-TEMP) for the core commands and [sulaweyo's ruby script](https://github.com/sulaweyo/r710-fan-control) for the idea of automating them.

**Note:** The key difference of this script is that it's based on the temperature of the CPUs' cores, not on the ambient temperature sensor on the server's motherboard. The R710 does not expose CPU temperature over IPMI, but other models do; this script should work with them nonetheless.
