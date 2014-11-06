Battray is a fairly simply tray icon to show your laptop’s battery status.
It's simple, easy, fairly environment-independent, and ‘just works’ without
tons of {Gnome,KDE,..} dependencies.

You can also configure it to play annoying sounds if your battery is getting low,
dim the screen when you switch from AC to battery, etc.


Installation
============
Battray requires Python 3.2+ with GTK (through [PyGObject][pygobject]). It runs
on FreeBSD, OpenBSD, and Linux.

Just type `./battray.py` to try it out; or run `./setup.py install` if you like it.


Commandline options
===================
- `-p`, `--platform`  
  Platform name, a list of platforms can be found in `battray/platforms.py`; by
  default this is automatically detected.

- `-i`, `--interval`  
  Polling interval in seconds; defaults to 15.


Configuration
=============
The default settings should be good for most people, but Battray is pretty
flexible and you can set it up as you like.
The default configuration is at `/usr/share/battray/battrayrc.py` or
`/usr/local/share/battray/battrayrc.py`, copy it to
`~/.config/battray/battrayrc.py` and edit it, there are a few comments to get
you started.  

The configuration file is run with `exec()`, so any Python code goes.


Available functions
-------------------
- `source_default()`  
  Source the default configuration file; this way you can append the default
  configuration file with your own commands, rather than completely overwrite it.

- `run(cmd)`  
  Run `cmd` (string) in shell. Note: no escaping will be done on the command.

- `play(sound)`  
   Play a `.wav` file.

- `play_once(sound, id)`  
  Play a `.wav` file once, until `reset_playonce()` is called for this `id`;
  `id` can be anything.

- `reset_play_once(id)`  
  Reset the `playonce` flag for the sound `id`, so it will be played again when
  `play_once()` is called for this `id`.

- `set_icon(file)`  
  Set icon to this `file`.

- `set_color('red|yellow|green')`  
  Fill battery icon with  this  color; it can either be the colour name `green`,
  `yellow`, or `red`, or a color code as int: `0xff0000ff` (the last byte is
  the alpha channel).

- `notify(msg, level)`  
  Send a desktop notification; you need a notification daemon (such as
  [dunst][dunst]) running to see this.

- `notify_once(msg, level, id)`  
  Send a desktop notification once; like `play_once()` (but the `id`s are not
  shared!).

- `reset_notify_once(id)`  
  Reset `notift_once()`, like `reset_play_once()`.



Available variables
-------------------
- `charging`  
  `True` if notebook is charging the battery, `False` if not, `None` if unknown.

- `ac`  
  `True` if notebook is connected to AC power, `False` if not, `None` if
  unknown.

- `percent`  
  Percentage of battery time remaining; `-1` if unknown.

- `lifetime`  
  Remaining battery time in minutes; `-1` if unknown.

- `switched_to`
  Set to 'battery' if we switched to battery since last poll, or 'ac' if we
  plugged the power in since the last poll. Otherwise set to `None`.



ChangeLog
=========

Version 2.0, to be released
---------------------------
- **Configuration files from previous versions are not compatible**.
- Use PyGobject instead of PyGTK.
- Better support for Linux.
- Only support Python 3 for now.
- Many changes.


Version 1.5, 2012-07-11
---------------------
- Bugfix: Fix FreeBSD CURRENT/10.
- Bugfix: Don't panic if there's no battery present (FreeBSD).
- Bugfix: Properly deal with unknown percentage/lifetime values.
- Feature: Add `playonce()` and `reset_playonce()` functions.
- Update default config.
- Update docs.


Version 1.4, 2011-09-26
---------------------
- Play sounds in a better way (Separate thread, not separate process).
- Update a few docs.


Version 1.3, 2011-07-24
---------------------
- **Configuration files from previous versions are not compatible**.
- Add Linux support (Submitted by Andy Mikhaylenko).
- Better configuration file/platform file importing.
- We now play a wav file with OSS instead of (trying to) use the PC speaker. Most laptops emulate a PC speaker, but the exact implementation varies from vendor to vendor and is the usual mess we've come to expect of these simple things :-(
- Add installer.
- Fix FreeBSD/amd64.


Version 1.2, 2009-10-22
---------------------
- New configuration file syntax, which is much more flexible.
- Add simple Makefile for easier installation & deinstallation.
- Add manpage.
- Various minor improvements.


Version 1.1, 2009-09-06
---------------------
- Battery icon is now green/yellow/red depending on battery life remaining.
- Battray will now warn you if battery level is below a certain percentage (See warn and warnMethod options in config.py).
- Reload configuration on SIGHUP.
- Added instructions on how to add platform.
- Add new icon to indicate error (Instead of no icon loaded at all).
- Fix FreeBSD platform, thanks to Eponasoft @ FreeBSD forums for reporting & testing.
- Some improvements on the OpenBSD platform.


Version 1.0, 2009-08-16
---------------------
- Initial release.



[dunst]: https://github.com/knopwob/dunst
[pygobject]: https://wiki.gnome.org/action/show/Projects/PyGObject
