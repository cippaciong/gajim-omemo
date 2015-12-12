# -*- coding: utf-8 -*-
# copyright 2015 bahtiar `kalkin-` gadimov <bahtiar@gadimov.de>
#
# this file is part of gajim.
#
# gajim is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published
# by the free software foundation; version 3 only.
#
# gajim is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with gajim.  if not, see <http://www.gnu.org/licenses/>.
#

import random

from common import caps_cache, gajim, ged
from plugins import GajimPlugin
from plugins.helpers import log, log_calls

from .iq import (BundleInformationAnnouncement, BundleInformationQuery,
                 DeviceListAnnouncement)
from .state import OmemoState
from .ui import make_ui

NS_OMEMO = 'eu.siacs.conversations.axolotl'
NS_DEVICE_LIST = NS_OMEMO + '.devicelist'
NS_NOTIFY = NS_DEVICE_LIST + '+notify'

iq_ids_to_callbacks = {}


class OmemoPlugin(GajimPlugin):

    omemo_states = {}

    @log_calls('OmemoPlugin')
    def init(self):
        self.events_handlers = {
            'message-received': (ged.CORE, self._pep_received),
            'raw-iq-received': (ged.PRECORE, self.handle_iq_received)
        }
        self.config_dialog = None
        self.gui_extension_points = {'chat_control_base':
                                     (self.connect_ui, None)}
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

    @log_calls('OmemoPlugin')
    def _pep_received(self, pep):

        event = pep.stanza.getTag('event')
        if not event:
            return

        items = pep.stanza.getTag('event').getTag('items', {'node':
                                                            NS_DEVICE_LIST})
        if items and len(items.getChildren()) == 1:

            account = pep.conn.name
            contact_jid = gajim.get_jid_without_resource(pep.fjid)

            log.info(account + ' ⇒ Received OMEMO pep for jid ' + contact_jid)

            devices = items.getChildren()[0].getTag('list').getChildren()
            devices_list = [dev.getAttr('id') for dev in devices]

            state = self.omemo_states[account]

            my_jid = gajim.get_jid_from_account(account)
            log.info('MY JID ' + my_jid)
            log.info('THEIR JID ' + contact_jid)

            if contact_jid == my_jid:
                log.info(state.name + ' ⇒ Received own device_list ' + str(
                    devices_list))
                state.add_own_devices(devices_list)

                if not state.own_device_id_published() or anydup(
                        state.own_devices):
                    # Our own device_id is not in the list, it could be
                    # overwritten by some other client?
                    # also remove duplicates
                    devices_list = list(set(state.own_devices))
                    devices_list.append(state.own_device_id)
                    self.publish_own_devices_list(state, devices_list)
            else:
                state.add_devices(contact_jid, devices_list)

    @log_calls('OmemoPlugin')
    def publish_own_devices_list(self, state, devices_list):
        log.info(state.name + ' ⇒ Publishing own devices_list ' + str(
            devices_list))
        iq = DeviceListAnnouncement(devices_list)
        gajim.connections[state.name].connection.send(iq)
        id_ = str(iq.getAttr('id'))
        log.info(state.name + ' ⇒ IQ id: ' + str(id_))
        iq_ids_to_callbacks[id_] = lambda event: log.info(event)

    @log_calls('OmemoPlugin')
    def connect_ui(plugin, chat_control):
        make_ui(plugin, chat_control)

    @log_calls('OmemoPlugin')
    def handle_iq_received(self, event):
        global iq_ids_to_callbacks
        id_ = str(event.stanza.getAttr("id"))
        account = event.conn.name
        if id_ in iq_ids_to_callbacks:
            log.info(account + ' ⇒ Got IQ with id ' + id_)
            try:
                iq_ids_to_callbacks[id_](event.stanza)
            except:
                raise
            finally:
                del iq_ids_to_callbacks[id_]

    @log_calls('OmemoPlugin')
    def query_prekey(self, contact):
        account = contact.account.name
        state = self.omemo_states[account]
        device_ids = state.device_ids_for(contact)

        for id_ in device_ids:
            log.info(account + ' ⇒ Query Bundle for ' + contact.jid + 'device'
                     + id_)
            iq = BundleInformationQuery(contact.jid, id_)
            gajim.connections[state.name].connection.send(iq)
            iq_id = str(iq.getAttr('id'))
            iq_ids_to_callbacks[iq_id] = random_prekey

    @log_calls('OmemoPlugin')
    def publish_bundle(self, account):
        state = self.omemo_states[account.name]
        iq = BundleInformationAnnouncement(state.bundle, state.own_device_id)
        gajim.connections[state.name].connection.send(iq)
        id_ = str(iq.getAttr("id"))
        iq_ids_to_callbacks[id_] = lambda event: log.info(event)


def random_prekey(event):
    prekeys = event.getTag('pubsub').getTag('items').getTag('item').getTag(
        'bundle').getTag('prekeys').getChildren()
    result = random.SystemRandom().choice(prekeys)
    log.info(event.name + ' ⇒ Random Prekey for  ' + str(event.getAttr('from'))
             + ': ' + str(result.getData()))


def anydup(thelist):
    seen = set()
    for x in thelist:
        if x in seen:
            return True
        seen.add(x)
    return False
