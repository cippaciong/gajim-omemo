# -*- coding: utf-8 -*-
#    otrmodule.py
#
# Copyright 2015 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
#
'''
Acronyms expander plugin.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 202015
:copyright: Copyright 2015 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
:license: GPL
'''

from common import caps_cache, gajim, ged
from plugins import GajimPlugin
from plugins.helpers import log, log_calls

from .state import OmemoState
from .ui import OmemoButton

NS_OMEMO = 'eu.siacs.conversations.axolotl'
NS_DEVICE_LIST = NS_OMEMO + '.devicelist'
NS_NOTIFY = NS_DEVICE_LIST + '+notify'


class OmemoPlugin(GajimPlugin):

    device_ids = {}
    omemo_states = {}

    @log_calls('OmemoPlugin')
    def init(self):
        self.events_handlers = {
            'message-received': (ged.CORE, self._pep_received)
        }
        self.config_dialog = None
        self.gui_extension_points = {'chat_control_base':
                                     (self.connect_ui, None)}
        log.info(gajim.contacts.get_accounts())
        for account in gajim.contacts.get_accounts():
            self.omemo_states[account] = OmemoState(account)

    @log_calls('OmemoPlugin')
    def activate(self):
        if NS_NOTIFY not in gajim.gajim_common_features:
            gajim.gajim_common_features.append(NS_NOTIFY)
        self._compute_caps_hash()

    @log_calls('OmemoPlugin')
    def deactivate(self):
        if NS_NOTIFY in gajim.gajim_common_features:
            gajim.gajim_common_features.remove(NS_NOTIFY)
        self._compute_caps_hash()

    @log_calls('OmemoPlugin')
    def _compute_caps_hash(self):
        for a in gajim.connections:
            gajim.caps_hash[a] = caps_cache.compute_caps_hash(
                [
                    gajim.gajim_identity
                ],
                gajim.gajim_common_features + gajim.gajim_optional_features[a])
            # re-send presence with new hash
            connected = gajim.connections[a].connected
            if connected > 1 and gajim.SHOW_LIST[connected] != 'invisible':
                gajim.connections[a].change_status(gajim.SHOW_LIST[connected],
                                                   gajim.connections[a].status)

    def _pep_received(self, pep):

        event = pep.stanza.getTag('event')
        if not event:
            return

        items = pep.stanza.getTag('event').getTag('items', {'node':
                                                            NS_DEVICE_LIST})
        if not items:
            # not a pep ignore it
            return

        if len(items.getChildren()) != 1:
            # should only have one item
            return

        account = pep.conn.name
        device_list = items.getChildren()[0].getTag('list').getChildren()

        contact_jid = gajim.get_jid_without_resource(pep.fjid)

        if account not in self.device_ids:
            self.device_ids[account] = {}

        if contact_jid not in self.device_ids[account]:
            self.device_ids[account][contact_jid] = []

        for device in device_list:
            device_id = device.getAttr('id')
            self.device_ids[account][contact_jid].append(device_id)

    @log_calls('OmemoPlugin')
    def connect_ui(self, chat_control):
        actions_hbox = chat_control.xml.get_object('actions_hbox')
        send_button = chat_control.xml.get_object('send_button')
        send_button_pos = actions_hbox.child_get_property(send_button,
                                                          'position')
        button = OmemoButton(self, chat_control.contact)
        actions_hbox.add_with_properties(button, 'position',
                                         send_button_pos - 2, 'expand', False)

    @log_calls('OmemoPlugin')
    def device_ids_for(self, contact):
        account = contact.account.name
        if account not in self.device_ids:
            log.debug('Account:' + str(account) + '¬∈ devices_ids')
            return None
        contact_jid = gajim.get_jid_without_resource(contact.get_full_jid())
        if contact_jid not in self.device_ids[account]:
            log.debug('Contact:' + contact_jid + '¬∈ devices_ids[' + account +
                      ']')
            return None

        log.info(self.device_ids[account])
        return self.device_ids[account][contact_jid]
