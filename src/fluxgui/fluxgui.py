#!/usr/bin/python2.7

"""A GUI applet for xflux."""

import appindicator
import errno
import gtk
import gtk.glade
import gconf
import sys
import time
import pexpect
import os
from xdg.DesktopEntry import DesktopEntry


__version__ = '1.1.8'

XFLUX_DEBUG = 0

def Warn(message):
    sys.stderr.write('Warning: %s\n' % message)

class Fluxgui(object):
    """Main application for fluxgui."""
    def __init__(self):
        self.pid_file = None
        self._check_pid()

        self.xflux = None

        self.settings = Settings()
        self.preferences = Preferences(self)
        self.indicator = Indicator(self)

        self.start_xflux()

        if not self.settings.latitude and not self.settings.zipcode:
            # Open preferences so user can enter settings.
            self.preferences.show()

    def _check_pid(self):
        """Reads from the pid file to see if fluxgui is already running. Updates
           the pid file with the current process's pid."""
        pid = os.getpid()
        pid_file = os.path.expanduser('~/.fluxgui.pid')

        running = False
        try:
            oldpid = int(open(pid_file).readline().rstrip())
            # Check for process existence.
            os.kill(oldpid, 0)
            running = True
        except IOError, err:
            if err.errno != errno.ENOENT:
                Warn('Failed to open pid file: %s' % err)
        except OSError, err:
            if err.errno != errno.ESRCH:
                Warn(err)
        except ValueError:
            # Corrupt pid_file, empty or not an int on first line.
            pass

        if running:
            print 'Fluxgui is already running, exiting.'
            sys.exit()

        try:
            file(pid_file, 'w').write('%d\n' % pid)
            self.pid_file = pid_file
        except IOError, e:
            Warn('Failed to write pid file: %s' % e)

    def start_xflux(self, unused_widget=None):
        """Starts xflux with the settings from the settings file."""
        args = []
        if self.settings.zipcode:
            args.extend(['-z', self.settings.zipcode])
        if self.settings.latitude:
            args.extend(['-l', self.settings.latitude])
            if self.settings.longitude:
                args.extend(['-g', self.settings.longitude])
        args.extend(['-k', str(self.settings.temperature), '-nofork'])

        self.indicator.show_pause()

        xflux = None
        try:
            # Terminate existing xfluxes to avoid conflict.
            os.system('killall xflux > /dev/null 2>&1')
            xflux = pexpect.spawn('/usr/bin/xflux', args)

            # Wait to see if xflux immediately terminated.
            time.sleep(0.1)
            if not xflux.isalive():
                if '-z' in args or '-l' in args:
                    # Something in the arguments made xflux close.
                    # xflux will close if run without -z or -l.
                    Warn(('xflux closed unexpectedly, check your fluxgui '
                          'settings.\nArguments: %s') % ' '.join(args))
                xflux = None

            if xflux and XFLUX_DEBUG:
                xflux.logfile = file('/tmp/fluxgui.log', 'w')
        except pexpect.ExceptionPexpect:
            print '\nError: Please install xflux in /usr/bin/ \n'
            self.exit()
        self.xflux = xflux

    def stop_xflux(self, unused_widget=None):
        """Stops xflux."""
        self.indicator.show_unpause()

        if self.xflux:
            self.xflux.terminate(force=True)
            self.xflux = None

    # Autostart code copied from AWN.
    def _get_autostart_file_path(self):
        """Returns the directory where autostart entries live."""
        autostart_dir = os.path.join(os.environ['HOME'], '.config',
                                     'autostart')
        return os.path.join(autostart_dir, 'fluxgui.desktop')

    def create_autostarter(self):
        """Adds an entry to the autostart directory to start fluxgui on
           startup."""
        autostart_file = self._get_autostart_file_path()
        autostart_dir = os.path.dirname(autostart_file)

        if not os.path.isdir(autostart_dir):
            # Create autostart directory.
            try:
                os.mkdir(autostart_dir)
            except OSError:
                print ('creation of autostart dir failed, please make it '
                       'yourself: %s') % autostart_dir
                self.exit()

        if not os.path.isfile(autostart_file):
            #create autostart entry
            starter_item = DesktopEntry(autostart_file)
            starter_item.set('Name', 'f.lux indicator applet')
            starter_item.set('Exec', 'fluxgui')
            starter_item.set('Icon', 'fluxgui')
            starter_item.set('X-GNOME-Autostart-enabled', 'true')
            starter_item.write()

    def delete_autostarter(self):
        """Removes the autostart entry for fluxgui."""
        autostart_file = self._get_autostart_file_path()
        if os.path.isfile(autostart_file):
            os.remove(autostart_file)

    def run(self):
        """Main entry path for GTK application."""
        gtk.main()

    def exit(self, unused_object=None):
        """Exits the application."""
        self.stop_xflux()
        os.unlink(self.pid_file)
        gtk.main_quit()
        sys.exit(0)


class Indicator(object):
    """Manages the GTK appindicator icon for fluxgui."""

    def __init__(self, fluxgui):
        self.fluxgui = fluxgui

        self.indicator = appindicator.Indicator('fluxgui-indicator',
          'fluxgui', appindicator.CATEGORY_APPLICATION_STATUS)
        self.indicator.set_status(appindicator.STATUS_ACTIVE)

        # Check for special Ubuntu themes (copied from lookit).
        try:
            default = gtk.gdk.screen_get_default()
            theme = default.get_setting('gtk-icon-theme-name')
        except:
            self.indicator.set_icon('fluxgui')
        else:
            if theme == 'ubuntu-mono-dark':
                self.indicator.set_icon('fluxgui-dark')
            elif theme == 'ubuntu-mono-light':
                self.indicator.set_icon('fluxgui-light')
            else:
                self.indicator.set_icon('fluxgui')

        self.pause_item = None
        self.unpause_item = None
        self._setup_menu()

    def _setup_menu(self):
        """Setups the menu for the indicator icon."""
        menu = gtk.Menu()

        pause_item = gtk.MenuItem('_Pause f.lux')
        pause_item.connect('activate', self.fluxgui.stop_xflux)
        pause_item.show()
        menu.append(pause_item)

        unpause_item = gtk.MenuItem('_Unpause f.lux')
        unpause_item.connect('activate', self.fluxgui.start_xflux)
        unpause_item.hide()
        menu.append(unpause_item)

        prefs_item = gtk.MenuItem('_Preferences')
        prefs_item.connect('activate', self.fluxgui.preferences.show)
        prefs_item.show()
        menu.append(prefs_item)

        sep_item = gtk.SeparatorMenuItem()
        sep_item.show()
        menu.append(sep_item)

        quit_item = gtk.MenuItem('Quit')
        quit_item.connect('activate', self.fluxgui.exit)
        quit_item.show()
        menu.append(quit_item)

        self.indicator.set_menu(menu)
        self.pause_item = pause_item
        self.unpause_item = unpause_item

    def show_unpause(self):
        """Shows the unpause xflux menu item and hides the other."""
        self.pause_item.hide()
        self.unpause_item.show()

    def show_pause(self):
        """Shows the pause xflux menu item and hides the other."""
        self.pause_item.show()
        self.unpause_item.hide()


class Preferences(object):
    """Manages the preferences GTK window to change preferences."""

    def __init__(self, fluxgui):
        self.fluxgui = fluxgui
        self.gladefile = os.path.join(os.path.dirname(os.path.dirname(
          os.path.realpath(__file__))), 'fluxgui/preferences.glade')
        self.window_tree = gtk.glade.XML(self.gladefile)

        self.window = self.window_tree.get_widget('window1')
        self.window.connect('destroy', self.hide)

        self.lat_setting = self.window_tree.get_widget('entry1')
        self.lat_setting.set_text(self.fluxgui.settings.latitude)

        self.lon_setting = self.window_tree.get_widget('entry3')
        self.lon_setting.set_text(self.fluxgui.settings.longitude)

        self.zip_setting = self.window_tree.get_widget('entry2')
        self.zip_setting.set_text(self.fluxgui.settings.zipcode)

        self.color_setting = self.window_tree.get_widget('combobox1')
        self.color_setting.set_active(int(self.fluxgui.settings.color_index))

        self.commandline_display = self.window_tree.get_widget('label6')

        self.close_button = self.window_tree.get_widget('button2')
        self.close_button.connect('clicked', self.hide)

        self.autostart = self.window_tree.get_widget('checkbutton1')
        self.autostart.set_active(self.fluxgui.settings.autostart == '1')

        if (not self.fluxgui.settings.latitude and
            not self.fluxgui.settings.zipcode):
            message = ('The f.lux indicator applet needs to know your latitude '
                       'and longitude or zipcode to work correctly. Please '
                       'fill either of them in on the next screen and then hit '
                       'enter.')
            dialog = gtk.MessageDialog(self.window,
                        gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO,
                        gtk.BUTTONS_OK, message)
            dialog.set_title('f.lux indicator applet')
            dialog.run()
            dialog.destroy()

    def show(self, unused_widget=None):
        """Shows the preferences window."""
        self.window.present()

        # Update command line display.
        text = None
        if self.fluxgui.xflux:
            text = 'Current commandline: xflux '
            text += ' '.join(self.fluxgui.xflux.args[1:-1])
        else:
            text = 'xflux is not currently running'
        self.commandline_display.set_text(text)


    def hide(self, unused_widget=None):
        """Hides the preferences window and saves settings."""
        self._update_settings()
        self.window.hide()

    def _update_settings(self):
        """Saves the preferences settings to the settings file."""
        changed = False
        if self.fluxgui.settings.latitude != self.lat_setting.get_text():
            self.fluxgui.settings.latitude = self.lat_setting.get_text()
            changed = True

        if self.fluxgui.settings.longitude != self.lon_setting.get_text():
            self.fluxgui.settings.longitude = self.lon_setting.get_text()
            changed = True

        if self.fluxgui.settings.zipcode != self.zip_setting.get_text():
            self.fluxgui.settings.zipcode = self.zip_setting.get_text()
            changed = True

        if self.fluxgui.settings.color_index != self.color_setting.get_active():
            self.fluxgui.settings.color_index = self.color_setting.get_active()
            changed = True

        if self.autostart.get_active():
            self.fluxgui.create_autostarter()
            self.fluxgui.settings.autostart = True
        else:
            self.fluxgui.delete_autostarter()
            self.fluxgui.settings.autostart = False

        if changed:
            self.fluxgui.stop_xflux()
            self.fluxgui.start_xflux()


class Settings(object):
    """Manages the storage of fluxgui settings via gconf. Does not do type
       conversion for settings."""

    def __init__(self):
        self.client = gconf.client_get_default()
        self.prefs_key = '/apps/fluxgui'
        self.client.add_dir(self.prefs_key, gconf.CLIENT_PRELOAD_NONE)

    @property
    def latitude(self):
        value = self.client.get_string(self.prefs_key + '/latitude')
        return value if value is not None else ''

    @latitude.setter
    def latitude(self, latitude):
        self.client.set_string(self.prefs_key + '/latitude', latitude)

    @property
    def longitude(self):
        value = self.client.get_string(self.prefs_key + '/longitude')
        return value if value is not None else ''

    @longitude.setter
    def longitude(self, longitude):
        self.client.set_string(self.prefs_key + '/longitude', longitude)

    @property
    def zipcode(self):
        value = self.client.get_string(self.prefs_key + '/zipcode')
        return value if value is not None else ''

    @zipcode.setter
    def zipcode(self, zipcode):
        self.client.set_string(self.prefs_key + '/zipcode', zipcode)

    @property
    def autostart(self):
        value = self.client.get_string(self.prefs_key + '/autostart')
        return value == '1'

    @autostart.setter
    def autostart(self, autostart):
        value = '1' if autostart else '0'
        self.client.set_string(self.prefs_key + '/autostart', value)

    @property
    def color_index(self):
        value = self.client.get_string(self.prefs_key + '/colortemp')
        return int(value) if value is not None else 1

    @color_index.setter
    def color_index(self, color_index):
        self.client.set_string(self.prefs_key + '/colortemp', str(color_index))

    @staticmethod
    def get_temperature_from_index(index):
        if index == 0:
            # Tungsten
            return 2700
        elif index == 1:
            # Halogen
            return 3400
        elif index == 2:
            # Fluorescent
            return 4200
        elif index == 3:
            # Daylight
            return 5000
        elif index == 4:
            # Off
            return 6500

        return 3400

    @property
    def temperature(self):
        return Settings.get_temperature_from_index(self.color_index)


def main():
    """Main entry point."""
    try:
        app = Fluxgui()
        app.run()
    except KeyboardInterrupt:
        app.exit()


if __name__ == '__main__':
    main()
