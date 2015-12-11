import gtk

from plugins.helpers import log


class OmemoButton(gtk.Button):

    def __init__(self, plugin, contact):
        super(OmemoButton, self).__init__(label='OMEMO')
        self.plugin = plugin
        self.contact = contact
        self.connect('clicked', self.on_click)

    def on_click(self, widget):
        devices = self.plugin.device_ids_for(self.contact)
        log.info(devices)
