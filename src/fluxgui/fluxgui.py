#!/usr/bin/python2.7

import appindicator
import errno
import gtk
import gtk.glade
import gconf
import sys
import pexpect
import os
from xdg.DesktopEntry import DesktopEntry


__version__ = '1.1.8'


class Fluxgui:
    def __init__(self):
        self.pid_file = None
        self._check_pid()

        self.indicator = Indicator(self)
        self.settings = Settings(self)

        self.xflux = None
        self.start_xflux()

        if not self.settings.latitude and not self.settings.zipcode:
            self.open_preferences('activate')

    def _check_pid(self):
        """Reads from the pid file to see if fluxgui is already running. Updates
           the pid file with the current process's pid."""
        pid = os.getpid()
        pid_file = os.path.expanduser('~/.fluxgui.pid')

        running = False
        if os.path.isfile(pid_file):
          try:
            oldpid = int(open(pid_file).readline().rstrip())
            try:
              # Check for process existence.
              os.kill(oldpid, 0)
              running = True
            except OSError as err:
              if err.errno == errno.ESRCH:
                # OSError: [Errno 3] No such process
                print 'stale pid_file, old pid: ', oldpid
          except ValueError:
            # Corrupt pid_file, empty or not an int on first line
            pass

        if running:
          print 'fluxgui is already running, exiting'
          sys.exit()
        else:
          file(pid_file, 'w').write('%d\n' % pid)
          self.pid_file = pid_file

    def start_xflux(self):
        args = ['-k', self.settings.color, '-nofork']
        if self.settings.zipcode:
            args.extend(['-z', self.settings.zipcode])
        if self.settings.latitude:
            args.extend(['-l', self.settings.latitude])
            if lon:
                args.extend(['-g', self.settings.longitude])

        try:
            self.xflux = pexpect.spawn('/usr/bin/xflux', args)

            #fout = file('/tmp/fluxlogstr.txt', 'w')
            #self.xflux.logfile = fout
        except pexpect.ExceptionPexpect:
            print '\nError: Please install xflux in /usr/bin/ \n'
            self.exit()

    def stop_xflux(self, item):
        self.indicator.item_turn_off.hide()
        self.indicator.item_turn_on.show()

        if self.xflux:
            # xflux is not running
            try:
                self.xflux.terminate(force=True)
            except Exception:
                # xflux has crashed in the meantime?
                pass

    def pause_xflux(self, item):
        self.indicator.item_turn_off.hide()
        self.indicator.item_turn_on.show()
        self.update_xflux('k=' + self.settings.get_color('4'))

    def unpause_xflux(self, item):
        self.indicator.item_turn_off.show()
        self.indicator.item_turn_on.hide()
        self.update_xflux('k=' + self.settings.color)

    def update_xflux(self, command):
        if self.xflux is None:
            self.start_xflux(self.settings.latitude, self.settings.longitude,
                         self.settings.zipcode, self.settings.color)
        else:
            self.xflux.sendline(command)

    def get_colortemp(self):
        if self.xflux:
            self.xflux.sendline('c')
            index = self.xflux.expect('Color.*')
            if index == 0:
                self.color = self.xflux.after[10:14]

    def preview_xflux(self, item):
      self.settings.set_colortemp(str(self.preferences.colsetting.get_active()))
      self.update_xflux('p')

    def open_preferences(self, item):
        self.get_colortemp()
        self.preferences = Preferences(self)

    #autostart code copied from AWN
    def get_autostart_file_path(self):
        autostart_dir = os.path.join(os.environ['HOME'], '.config',
                                     'autostart')
        return os.path.join(autostart_dir, 'fluxgui.desktop')

    def create_autostarter(self):
        autostart_file = self.get_autostart_file_path()
        autostart_dir = os.path.dirname(autostart_file)

        if not os.path.isdir(autostart_dir):
            #create autostart dir
            try:
                os.mkdir(autostart_dir)
            except Exception, e:
                print 'creation of autostart dir failed, please make it yourself: %s' % autostart_dir
                raise e

        if not os.path.isfile(autostart_file):
            #create autostart entry
            starter_item = DesktopEntry(autostart_file)
            starter_item.set('Name', 'f.lux indicator applet')
            starter_item.set('Exec', 'fluxgui')
            starter_item.set('Icon', 'fluxgui')
            starter_item.set('X-GNOME-Autostart-enabled', 'true')
            starter_item.write()
            self.settings.set_autostart(True)

    def delete_autostarter(self):
        autostart_file = self.get_autostart_file_path()
        if os.path.isfile(autostart_file):
            os.remove(autostart_file)
            self.settings.set_autostart(False)

    def run(self):
        gtk.main()

    def exit(self, unused_widget, unused_data=None):
        self.stop_xflux('activate')
        os.unlink(self.pid_file)
        gtk.main_quit()
        sys.exit(0)

class Indicator:

    def __init__(self, main):
        self.main = main
        self.setup_indicator()

    def setup_indicator(self):
        self.indicator = appindicator.Indicator(
          'fluxgui-indicator',
          'fluxgui',
          appindicator.CATEGORY_APPLICATION_STATUS)
        self.indicator.set_status(appindicator.STATUS_ACTIVE)

        # Check for special Ubuntu themes. copied from lookit

        try:
            theme = gtk.gdk.screen_get_default().get_setting('gtk-icon-theme-name')
        except:
            self.indicator.set_icon('fluxgui')
        else:
          if theme == 'ubuntu-mono-dark':
              self.indicator.set_icon('fluxgui-dark')
          elif theme == 'ubuntu-mono-light':
              self.indicator.set_icon('fluxgui-light')
          else:
              self.indicator.set_icon('fluxgui')

        self.indicator.set_menu(self.setup_menu())

    def setup_menu(self):
        menu = gtk.Menu()

        self.item_turn_off = gtk.MenuItem('_Pause f.lux')
        self.item_turn_off.connect('activate', self.main.pause_xflux)
        self.item_turn_off.show()
        menu.append(self.item_turn_off)

        self.item_turn_on = gtk.MenuItem('_Unpause f.lux')
        self.item_turn_on.connect('activate', self.main.unpause_xflux)
        self.item_turn_on.hide()
        menu.append(self.item_turn_on)

        item = gtk.MenuItem('_Preferences')
        item.connect('activate', self.main.open_preferences)
        item.show()
        menu.append(item)

        item = gtk.SeparatorMenuItem()
        item.show()
        menu.append(item)

        item = gtk.MenuItem('Quit')
        item.connect('activate', self.main.exit)
        item.show()
        menu.append(item)

        return menu

    def main(self):
        gtk.main()


class Preferences:

    def __init__(self, main):
        self.main = main
        self.gladefile = os.path.join(os.path.dirname(os.path.dirname(
          os.path.realpath(__file__))), 'fluxgui/preferences.glade')
        self.wTree = gtk.glade.XML(self.gladefile)

        self.window = self.wTree.get_widget('window1')
        self.window.connect('destroy', self.delete_event)

        self.latsetting = self.wTree.get_widget('entry1')
        self.latsetting.set_text(self.main.settings.latitude)
        self.latsetting.connect('activate', self.delete_event)

        self.lonsetting = self.wTree.get_widget('entry3')
        self.lonsetting.set_text(self.main.settings.longitude)
        self.lonsetting.connect('activate', self.delete_event)

        self.zipsetting = self.wTree.get_widget('entry2')
        self.zipsetting.set_text(self.main.settings.zipcode)
        self.zipsetting.connect('activate', self.delete_event)

        self.colsetting = self.wTree.get_widget('combobox1')
        self.colsetting.set_active(int(self.main.settings.colortemp))

        self.colordisplay = self.wTree.get_widget('label6')
        if self.main.color:
            self.colordisplay.set_text('Current color temperature: '
                                       + self.main.color + 'K')

        self.previewbutton = self.wTree.get_widget('button1')
        self.previewbutton.connect('clicked', self.main.preview_xflux)


        self.closebutton = self.wTree.get_widget('button2')
        self.closebutton.connect('clicked', self.delete_event)

        self.autostart = self.wTree.get_widget('checkbutton1')
        if self.main.settings.autostart == '1':
            self.autostart.set_active(True)
        else:
            self.autostart.set_active(False)

        if not self.main.settings.latitude and not self.main.settings.zipcode:
            message = ('The f.lux indicator applet needs to know your latitude '
                       'and longitude or zipcode to work correctly. Please '
                       'fill either of them in on the next screen and then hit '
                       'enter.')
            md = gtk.MessageDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_INFO, gtk.BUTTONS_OK, message)
            md.set_title('f.lux indicator applet')
            md.run()
            md.destroy()
            self.window.show()
        else:
            self.window.show()

    def delete_event(self, widget, unused_data=None):
        if self.main.settings.latitude != self.latsetting.get_text():
            self.main.settings.set_latitude(self.latsetting.get_text())

        if self.main.settings.longitude != self.lonsetting.get_text():
            self.main.settings.set_longitude(self.lonsetting.get_text())

        if self.main.settings.zipcode != self.zipsetting.get_text():
            self.main.settings.set_zipcode(self.zipsetting.get_text())

        if self.main.settings.colortemp != str(self.colsetting.get_active()):
            self.main.settings.set_colortemp(str(self.colsetting.get_active()))

        if self.autostart.get_active():
            self.main.create_autostarter()
        else:
            self.main.delete_autostarter()

        self.window.hide()
        return False

    def main(self):
        gtk.main()


class Settings:

    def __init__(self, main):
        self.main = main
        self.client = gconf.client_get_default()
        self.prefs_key = '/apps/fluxgui'
        self.client.add_dir(self.prefs_key, gconf.CLIENT_PRELOAD_NONE)

        self.autostart = self.client.get_string(self.prefs_key + '/autostart')
        self.latitude = self.client.get_string(self.prefs_key + '/latitude')
        self.longitude = self.client.get_string(self.prefs_key + '/longitude')
        self.zipcode = self.client.get_string(self.prefs_key + '/zipcode')
        self.colortemp = self.client.get_string(self.prefs_key + '/colortemp')
        self.color = self.get_color(self.colortemp)

        if self.latitude is None:
            self.latitude = ''

        if self.longitude is None:
            self.longitude = ''

        if self.zipcode is None:
            self.zipcode = ''

        if not self.colortemp:
            self.colortemp = '1'

        if not self.autostart:
            self.autostart = '0'

    def set_latitude(self, latitude):
        self.client.set_string(self.prefs_key + '/latitude', latitude)
        self.latitude = latitude

        command = 'l=' + latitude
        self.main.update_xflux(command)

    def set_longitude(self, longitude):
        self.client.set_string(self.prefs_key + '/longitude', longitude)
        self.longitude = longitude

        command = 'g=' + longitude
        self.main.update_xflux(command)

    def set_zipcode(self, zipcode):
        self.client.set_string(self.prefs_key + '/zipcode', zipcode)
        self.zipcode = zipcode

        command = 'z=' + zipcode
        self.main.update_xflux(command)

    def get_color(self, colortemp):
        color = '3400'
        if colortemp == '0':
            # Tungsten
            color = '2700'
        elif colortemp == '1':
            # Halogen
            color = '3400'
        elif colortemp == '2':
            # Fluorescent
            color = '4200'
        elif colortemp == '3':
            # Daylight
            color = '5000'
        elif colortemp == '4':
            # Off
            color = '6500'

        return color

    def set_colortemp(self, colortemp):
        color = self.get_color(colortemp)

        self.client.set_string(self.prefs_key + '/colortemp', colortemp)
        self.colortemp = colortemp
        self.color = color

        command = 'k=' + color
        self.main.update_xflux(command)

    def set_autostart(self, autostart):
        if autostart:
            self.client.set_string(self.prefs_key + '/autostart', '1')
            self.autostart = '1'
        else:
            self.client.set_string(self.prefs_key + '/autostart', '0')
            self.autostart = '0'

    def main(self):
        gtk.main()


if __name__ == '__main__':
    try:
        app = Fluxgui()
        app.run()
    except KeyboardInterrupt:
        app.exit()

