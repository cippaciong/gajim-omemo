import logging

import gtk

log = logging.getLogger('gajim.plugin_system.omemo')

# from plugins.helpers import log


class PreKeyButton(gtk.Button):
    def __init__(self, plugin, contact):
        super(PreKeyButton, self).__init__(label='Get Missing Prekeys')
        self.plugin = plugin
        self.contact = contact
        self.connect('clicked', self.on_click)

    def on_click(self, widget):
        self.plugin.query_prekey(self.contact)


class ClearDevicesButton(gtk.Button):
    def __init__(self, plugin, contact):
        super(ClearDevicesButton, self).__init__(label='Clear Devices')
        self.plugin = plugin
        self.contact = contact
        self.connect('clicked', self.on_click)

    def on_click(self, widget):
        self.plugin.clear_device_list(self.contact)


class Checkbox(gtk.CheckButton):
    def __init__(self, plugin, contact):
        super(Checkbox, self).__init__(label='OMEMO')
        self.plugin = plugin
        self.contact = contact
        self.connect('clicked', self.on_click)

    def on_click(self, widget):
        enabled = self.get_active()
        log.info('Clicked ' + str(enabled))
        if enabled:
            self.plugin.omemo_enable_for(self.contact)
        else:
            self.plugin.omemo_disable_for(self.contact)


def _add_widget(widget, chat_control):
    actions_hbox = chat_control.xml.get_object('actions_hbox')
    send_button = chat_control.xml.get_object('send_button')
    send_button_pos = actions_hbox.child_get_property(send_button, 'position')
    actions_hbox.add_with_properties(widget, 'position', send_button_pos - 2,
                                     'expand', False)


class Ui(object):
    def __init__(self, plugin, chat_control):
        contact = chat_control.contact
        self.prekey_button = PreKeyButton(plugin, contact)
        self.checkbox = Checkbox(plugin, contact)
        self.clear_button = ClearDevicesButton(plugin, contact)

        enabled = plugin.has_omemo(contact)
        self.toggle_omemo(enabled)

        _add_widget(self.prekey_button, chat_control)
        _add_widget(self.checkbox, chat_control)
        _add_widget(self.clear_button, chat_control)

    def toggle_omemo(self, enabled):
        if enabled:
            self.checkbox.set_no_show_all(False)
            self.checkbox.show()
            self.prekey_button.set_no_show_all(False)
            self.prekey_button.show()
        else:
            self.checkbox.set_no_show_all(True)
            self.checkbox.hide()
            self.prekey_button.set_no_show_all(True)
            self.prekey_button.hide()

    def activate_omemo(self):
        self.checkbox.set_active(True)
