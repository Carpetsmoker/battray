#
# http://code.arp242.net/battray
#
# Copyright © 2008-2017 Martin Tournoij <martin@arp242.net>
# See below for full copyright
#
# Return False on error
#
# Or return tuple with:
#
# bats:      Number of batteries (only 0 and 1 is acted on, more batteries are
#            ignored for now).
# ac:        Connected to AC? Boolean, None if unknown.
# charging:  Are we charging the battery? Boolean, None if unknown.
# percent:   Battery power remaining in percent (0-100), integer, None if unknown.
# lifetime:  Battery time remaining in minutes, or time to full charge, integer,
#            None if unknown.
#

import logging, sys, os, glob

def find():
    platform = ''
    for char in sys.platform:
        if char in '1234567890': break
        platform += char

    fun = globals().get(platform, None)
    if fun is None:
        print('Error: unable to get platform for %s' % platform, file=sys.stderr)
        sys.exit(1)

    logging.info('Using platform {}'.format(fun.__name__))
    return fun


def freebsd():
    """ FreeBSD, should work at least for 8 and newer """
    import subprocess

    o = subprocess.Popen(['acpiconf', '-i0'], stdout=subprocess.PIPE).communicate()[0].decode()

    for line in o.split('\n'):
        if line.find(':') == -1:
            continue
        (key, value) = line.split(':', 1)

        if key.strip() == 'Remaining capacity':
            percent = int(value.strip().replace('%', ''))
        elif key.strip() == 'Remaining time':
            if value.strip() == 'unknown':
                lifetime = -1
            else:
                lifetime = value.strip().replace(':', '.')
                lifetime = int(int(lifetime[0]) * 60 + int(lifetime[2]) * 10)
        elif key.strip() == 'State':
            if value.strip() == 'charging':
                charging = True
            else:
                charging = False
        elif key.strip() == 'Present rate':
            if value.strip() == '0 mW' or value.strip().endswith('(0 mW)'):
                ac = True
            else:
                ac = False
        elif key.strip() == 'State' and value.strip() == 'not present':
            ac = None

    if charging:
        ac = True

    return (1, ac, charging, percent, lifetime)


def openbsd():
    """ OpenBSD; should work with all versions since 4 (possibly earlier) """

    import subprocess

    ac = charging = None
    percent = lifetime = 999

    def sysctl(name):
        o = subprocess.Popen(['/sbin/sysctl', name], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE).communicate()[0].decode()
        try:
            (name, value) = o.split('=')
        except ValueError:
            value = None
        return value

    o = subprocess.Popen(['/usr/sbin/apm', '-balm'], stdout=subprocess.PIPE).communicate()[0]
    (bstat, percent, lifetime, ac) = o.decode().split()

    if bstat == '4':
        return (0, 1, 0, 0, 0)

    if ac == '0':
        ac = False
    elif ac == '1':
        ac = True
    else:
        ac = None

    # apm output is not always reliable ...
    b = sysctl('hw.sensors.acpibat0.raw0')
    if b and b[:1] == '2':
        charging = True
    else:
        charging = False

    percent = int(percent)
    if lifetime == 'unknown':
        lifetime = -1
    else:
        lifetime = float(lifetime) * 60

    return (1, ac, charging, percent, lifetime)


def linux():
    """  Linux, being Linux, has several incompatible ways of doing this. """

    for linux_modes in ['linux_upower', 'linux_sysfs']:
        result = globals().get(linux_modes)()
        if result != False:
            logging.info('Using {}'.format(linux_modes))
            return result
    return False


def linux_sysfs():
    """ Use data from sysfs """
    SYSFS = "/sys/class/power_supply"

    def _gets(bat, attr):
        path = os.path.join(SYSFS, bat, attr)
        try:
            with open(path) as f: return "\n".join(f.readlines()).strip()
        except:
            return ""

    def _get(bat, attr):
        return int(_gets(bat, attr))

    def _ttl(state, max, now, rate):
        try:
            if state: ttl = 3600 * (max - now) / rate
            else: ttl = 3600 * now / rate
        except:
            ttl = False
        return ttl

    batteries = {}
    for entry in os.listdir(SYSFS):
        if "BAT" in entry:
            print('e:', entry)
            batteries[entry] = {'id': entry}

    for bat in batteries:
        status = _gets(bat, "status")
        charging = status == "Charging"
        # microvolts
        voltage = _get(bat, "voltage_now") / 1000
        if os.path.exists(os.path.join(SYSFS, bat, "energy_full")):
            # microwatthours
            max      = _get(bat, "energy_full") / 1000
            max_orig = _get(bat, "energy_full_design") / 1000
            now      = _get(bat, "energy_now") / 1000
            rate     = _get(bat, "power_now") / 1000
        else:
            # microamperehours
            max      = _get(bat, "charge_full") / voltage
            max_orig = _get(bat, "charge_full_design") / voltage
            now      = _get(bat, "charge_now") / voltage
            rate     = _get(bat, "charge_now") / voltage

        batteries[bat]['charging']  = charging
        batteries[bat]['percent']   = (now / max) * 100
        batteries[bat]['wearlevel'] = (max / max_orig) * 100
        batteries[bat]['now']       = now
        batteries[bat]['rate']      = rate
        batteries[bat]['ttl']       = _ttl(charging, max, now, rate)

    percent = ttl = 0
    charging = False
    for bat in batteries:
        percent  += batteries[bat]['percent']
        ttl      += batteries[bat]['ttl']
        charging |= batteries[bat]['charging']
    percent /= len(batteries)

    ac = any (map (lambda x: int(open(x).read().strip())==1, glob.glob ("/sys/class/power_supply/AC*/online")))

    return (1, ac, charging, percent, ttl)


def linux_upower():
    """ Linux with UPower; http://upower.freedesktop.org/docs/Device.html """
    try:
        import dbus
    except ImportError:
        #print('battray: "import dbus" failed; not trying UPower', file=sys.stderr)
        #print('battray: if you would like to use UPower then install dbus-python:', file=sys.stderr)
        print('battray: "import dbus" failed; this is required for Linux; install it with:', file=sys.stderr)
        print('battray: pip install dbus-python', file=sys.stderr)
        return False

    bus = dbus.SystemBus()

    # trigger refresh
    proxy = bus.get_object('org.freedesktop.UPower', '/org/freedesktop/UPower/devices/line_power_AC')
    dbus_method = proxy.get_dbus_method('Refresh', 'org.freedesktop.UPower.Device')
    dbus_method("None")

    upower = bus.get_object('org.freedesktop.UPower', '/org/freedesktop/UPower/devices/DisplayDevice')
    #upower = bus.get_object('org.freedesktop.UPower', '/org/freedesktop/UPower/devices/battery_BAT1')
    iface = dbus.Interface(upower, 'org.freedesktop.DBus.Properties')
    info = iface.GetAll('org.freedesktop.UPower.Device')

    percent = float(info['Percentage'])
    state = int(info['State'])
    charging = False
    if state == 1:
        ac = True
        charging = True
    elif state == 2:
        ac = False
    elif state == 4:
        ac = True
    else:
        ac = None

    if charging:
        lifetime = int(info['TimeToFull']) / 60
    else:
        lifetime = int(info['TimeToEmpty']) / 60

    return (1, ac, charging, percent, lifetime)


# The MIT License (MIT)
#
# Copyright © 2008-2017 Martin Tournoij
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# The software is provided "as is", without warranty of any kind, express or
# implied, including but not limited to the warranties of merchantability,
# fitness for a particular purpose and noninfringement. In no event shall the
# authors or copyright holders be liable for any claim, damages or other
# liability, whether in an action of contract, tort or otherwise, arising
# from, out of or in connection with the software or the use or other dealings
# in the software.
