# encoding: utf-8
#
# http://code.arp242.net/battray
#
# Copyright © 2008-2017 Martin Tournoij <martin@arp242.net>
# See below for full copyright
#

import logging, os, sys
from gi.repository import Gtk, GLib, GdkPixbuf

from . import platforms, sound
__all__ = ['platforms', 'sound', 'Battray']


def find_config(configfile=None, datadir=None):
    xdg_config_home = '{}/battray'.format(os.getenv('XDG_CONFIG_HOME') or os.path.expanduser('~/.config'))
    xdg_datadirs = (os.getenv('XDG_DATA_DIRS') or '/usr/local/share:/usr/share').split(':')

    default_config = None

    if datadir is not None:
        f = '{}/battray/battrayrc.py'.format(datadir)
        if os.path.exists(f):
            default_config = f

    for xdg_datadir in xdg_datadirs:
        if datadir is None:
            d = '{}/battray'.format(xdg_datadir)
            if os.path.exists(d):
                datadir = d

        if default_config is None:
            f = '{}/battray/battrayrc.py'.format(xdg_datadir)
            if os.path.exists(f):
                default_config = f

    # XDG failed; try to load from cwd
    mydir = os.path.dirname(os.path.realpath(sys.argv[0]))
    if default_config is None:
        f = '{}/data/battrayrc.py'.format(mydir)
        if os.path.exists(f): default_config = f

    if configfile is None:
        f = '{}/battrayrc.py'.format(xdg_config_home)
        if os.path.exists(f):
            configfile = f
        else:
            configfile = default_config

    if configfile is None:
        raise Exception("Can't find config file")

    if datadir is None:
        d = '{}/data'.format(mydir)
        if os.path.exists(d): datadir = d

    if datadir is None:
        raise Exception("Can't find data dir")

    logging.info('Using {}'.format(configfile))
    return configfile, datadir, default_config


def set_proctitle(title):
    try:
        # This is probably the best way to do this, but I don't want to force an
        # external dependency on this C module...
        import setproctitle
        setproctitle.setproctitle(title)
    except ImportError:
        import ctypes, ctypes.util

        libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('c'))
        title_bytes = title.encode(sys.getdefaultencoding(), 'replace')
        buf = ctypes.create_string_buffer(title_bytes)

        # BSD, maybe also OSX?
        try:
            libc.setproctitle(ctypes.create_string_buffer(b"-%s"), buf)
            return
        except AttributeError:
            pass

        # Linux
        try:
            libc.prctl(15, buf, 0, 0, 0)
            return
        except AttributeError:
            pass


class Battray(object):
    def __init__(self, interval=None, configfile=None, platform=None, datadir=None):
        self.configfile, self.datadir, self.default_config = find_config(configfile, datadir)

        if platform:
            self.platform = getattr(platforms, platform, None)
            if self.platform is None:
                logging.error("No such platform: `{}'".format(platform))
                sys.exit(1)
        else:
            self.platform = platforms.find()
        self.data = self.played = self.notified = {}

        self.icon = Gtk.StatusIcon()
        self.icon.set_name('Battray')
        
        self.menu = Gtk.Menu()
        refresh = Gtk.MenuItem.new_with_label('Refresh')
        refresh.connect('activate', self.cb_update)
        self.menu.append(refresh)

        about = Gtk.MenuItem.new_with_label('About')
        about.connect('activate', self.cb_about)
        self.menu.append(about)

        quit = Gtk.MenuItem.new_with_label('Quit')
        quit.connect('activate', self.cb_destroy)
        self.menu.append(quit)

        self.icon.connect('activate', self.cb_update)
        self.icon.connect('popup-menu', self.cb_popup_menu)
        self.icon.set_visible(True)

        self.update_status()
        GLib.timeout_add_seconds(interval or 15, self.update_status)


    def update_status(self):
        try:
            logging.info('Getting status ...')
            prev_ac = self.data.get('ac')
            (self.data['bats'], self.data['ac'], self.data['charging'],
                self.data['percent'], self.data['lifetime']) = self.platform()

            logging.info(self.data)

            if self.data['ac'] and not prev_ac:
                self.data['switched_to'] = 'ac'
            elif not self.data['ac'] and prev_ac:
                self.data['switched_to'] = 'battery'
            else:
                self.data['switched_to'] = None

            icon = color = None
            def set_icon(i): nonlocal icon; icon = i
            def set_color(c): nonlocal color; color = c

            def play_once(f, k):
                if self.played.get(k): return
                self.played[k] = True
                sound.play('{}/{}'.format(self.datadir, f))

            def notify_once(m, l, k):
                if self.notified.get(k): return
                self.notified[k] = True
                self.notify(m, l)

            def reset_play_once(k):
                if self.played.get(k): self.played[k] = False

            def reset_notify_once(k):
                if self.notified.get(k): self.notified[k] = False

            args = {
                'bats': self.data['bats'],
                'ac': self.data['ac'],
                'charging': self.data['charging'],
                'percent': self.data['percent'],
                'lifetime': self.data['lifetime'],
                'switched_to': self.data['switched_to'],
                'set_icon': set_icon,
                'set_color': set_color,
                'play': lambda f: sound.play('{}/{}'.format(self.datadir, f)),
                'play_once': play_once,
                'reset_play_once': reset_play_once,
                'notify': self.notify,
                'notify_once': notify_once,
                'reset_notify_once': reset_notify_once,
                'run': self.run,
            }

            def source_default():
                exec(open(self.default_config, 'r').read(), args)

            args.update({'source_default': source_default})
            exec(open(self.configfile, 'r').read(), args)

            self.set_icon(icon, color)
            self.set_tooltip()
        except:
            print('battray error: {}'.format(sys.exc_info()[1]))
            if logging.root.level == logging.DEBUG:
                import traceback
                traceback.print_tb(sys.exc_info()[2])
        return True # Required for GLib.timeout_add_seconds


    def run(self, cmd):
        import subprocess
        try:
            o = subprocess.Popen([cmd], stdout=subprocess.PIPE, shell=True).communicate()[0]
            logging.info(o)
        except OSError:
            logging.warning("something went wrong executing `{}'\n{}\n{}".format(
                cmd, o, sys.exc_info()[1]))


    def notify(self, msg, urgency='normal'):
        try:
            # TODO: This is BSD license, so we could just include it
            import notify2
        except ImportError:
            logging.warning("pynotify2 not found; desktop notifications won't work")
            return

        notify2.init('battray')
        n = notify2.Notification('Battray', msg, '{}/icon.png'.format(self.datadir))
        n.set_urgency({
            'low': notify2.URGENCY_LOW,
            'normal': notify2.URGENCY_NORMAL,
            'critical': notify2.URGENCY_CRITICAL,
        }.get(urgency))
        n.show()


    def set_icon(self, iconf, color=None):
        if iconf.startswith('/'):
            iconpath = iconf
        else:
            iconpath = '{}/{}'.format(self.datadir, iconf)
        if '.' not in iconpath: iconpath += '.png'
        logging.info("setting icon to `{}'".format(iconpath))

        if color is None:
            self.icon.set_from_file(iconpath)
            return

        colors = {
            'green': 0x1eff19ff,
            'orange': 0xdeb700ff,
            'red': 0xff0c00ff,
            'yellow': 0xeeff2dff,
        }
        if color in colors: color = colors[color]

        fill = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 1, 1)
        fill.fill(color)

        trans = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 1, 1)
        trans.fill(0)

        icon = GdkPixbuf.Pixbuf.new_from_file(iconpath)

        # TODO: Figure out the longest sequence of pixels to fill, and use that
        # value to determine how much to fill up; this way it's easier to make
        # different icons
        fill_amount = int(round(self.data['percent'] / 4))

        # TODO: This is neat, but go for a more readable method
        # Got it from: http://stackoverflow.com/a/1335618/660921
        for row_num, row in enumerate(zip(*(iter(icon.get_pixels()),) * icon.get_rowstride())):
            for col_num, pixel in enumerate(zip(*(iter(row),) * 4)):
                r, g, b, a = pixel
                if not (r == 255 and g == 0 and b == 255): continue

                if col_num <= fill_amount:
                    fill.copy_area(0, 0, 1, 1, icon, col_num, row_num)
                else:
                    trans.copy_area(0, 0, 1, 1, icon, col_num, row_num)

        self.icon.set_from_pixbuf(icon)


    def set_tooltip(self):
        bats = self.data['bats']
        ac = self.data['ac']
        charging = self.data['charging']
        percent = self.data['percent']
        lifetime = self.data['lifetime']

        if bats == 0:
            self.icon.set_tooltip_text('No battery present.')
            return

        text = []
        if ac == None:
            text.append('Cannot get battery status.\n')
        elif ac:
            text.append('Connected to AC power.\n')
        elif not ac:
            text.append('Running on battery.\n')

        if percent == -1:
            text.append('Cannot get battery percentage status.\n')
        else:
            text.append('{:.4g}% battery power remaining.\n'.format(percent))

        if lifetime == -1:
            text.append('Unknown lifetime remaining.\n')
        elif charging:
            hours = int(lifetime // 60.0)
            minutes = int(lifetime % 60)
            text.append('Approximately {:02}:{:02} remaining.\n'.format(hours, minutes))
        elif not ac:
            hours = int(lifetime // 60.0)
            minutes = int(lifetime % 60)
            text.append('Approximately {:02}:{:02} remaining.\n'.format(hours, minutes))

        if charging == None:
            pass
        elif charging == True:
            text.append('Charging battery.')
        else:
            text.append('Not charging battery.')

        self.icon.set_tooltip_text(''.join(text))


    def cb_destroy(self, widget, data=None):
        self.icon.set_visible(False)
        Gtk.main_quit()
        return False


    def cb_update(self, widget, data=None):
        self.update_status()


    def cb_popup_menu(self, widget, button, time, data=None):
        self.menu.show_all()
        self.menu.popup(None, None, Gtk.StatusIcon.position_menu, self.icon, button, time)


    def cb_about(self, widget, data=None):
        about = Gtk.AboutDialog()
        about.set_artists(['Martin Tournoij <martin@arp242.net>', 'Keith W. Blackwell'])
        about.set_authors(['Martin Tournoij <martin@arp242.net>'])
        about.set_comments('Simple program that displays a tray icon to inform you on your notebooks battery status.')
        about.set_copyright('Copyright © 2008-2017 Martin Tournoij <martin@arp242.net>')
        about.set_license_type(Gtk.License.MIT_X11)
        about.set_logo(GdkPixbuf.Pixbuf.new_from_file('{}/icon.png'.format(self.datadir)))
        about.set_program_name('Battray')
        about.set_version('2.3')
        about.set_website('http://code.arp242.net/battray')

        about.run()
        about.destroy()

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
