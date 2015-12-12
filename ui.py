import gtk



class OmemoButton(gtk.Button):

    def __init__(self, plugin, contact):
        super(OmemoButton, self).__init__(label='OMEMO')
        self.plugin = plugin
        self.contact = contact
        self.connect('clicked', self.on_click)

    def on_click(self, widget):
        self.plugin.query_bundle(self.contact)
