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

import logging

from common import caps_cache, gajim, ged
from plugins import GajimPlugin
from plugins.helpers import log_calls

from .iq import (BundleInformationAnnouncement, BundleInformationQuery,
                 DeviceListAnnouncement, OmemoMessage, successful,
                 unpack_device_bundle, unpack_message)
from .state import NoValidSessions, OmemoState
from .ui import Ui

NS_OMEMO = 'eu.siacs.conversations.axolotl'
NS_DEVICE_LIST = NS_OMEMO + '.devicelist'
NS_NOTIFY = NS_DEVICE_LIST + '+notify'

iq_ids_to_callbacks = {}

log = logging.getLogger('gajim.plugin_system.omemo')


class OmemoPlugin(GajimPlugin):

    omemo_states = {}

    published_bundles = {}

    ui_list = {}

    @log_calls('OmemoPlugin')
    def init(self):
        self.events_handlers = {
            'message-received': (ged.PRECORE, self.message_received),
            'raw-iq-received': (ged.PRECORE, self.handle_iq_received),
            'our-show': (ged.PRECORE, self.handle_show),
            'stanza-message-outgoing':
            (ged.PRECORE, self.handle_outgoing_msgs),
        }
        self.config_dialog = None
        self.gui_extension_points = {'chat_control_base':
                                     (self.connect_ui, None)}
        for account in gajim.contacts.get_accounts():
            self.omemo_states[account] = OmemoState(account)

    @log_calls('OmemoPlugin')
    def handle_show(self, show):
        account = show.conn.name
        if show.show != 'offline' and account not in self.published_bundles:
            state = self.omemo_states[account]
            self.publish_bundle(state)
            self.published_bundles[account] = True
        elif show.show == 'offline':
            self.published_bundles.pop(account, None)

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
    def message_received(self, msg):
        if msg.stanza.getTag('event'):
            if self._device_list_update(msg):
                return
        if msg.stanza.getTag('encrypted', namespace=NS_OMEMO):
            msgtext = self.decrypt_msg(msg)
            if not msgtext:
                return
            msg.msgtxt = msgtext
            msg.stanza.setBody(msg.msgtxt)
            log.debug(msg.conn.name + ' → ' + msg.msgtxt)
            return False

    @log_calls('OmemoPlugin')
    def decrypt_msg(self, msg):
        account = msg.conn.name
        state = self.omemo_states[account]
        log.debug(account + ' ⇒ OMEMO msg received')
        result = unpack_message(msg.stanza)
        result['sender_jid'] = gajim.get_jid_without_resource(msg.fjid)
        plaintext = state.decrypt_msg(result)
        return plaintext

    @log_calls('OmemoPlugin')
    def _device_list_update(self, msg):
        event_node = msg.stanza.getTag('event')
        if not event_node:
            log.info('Event node empty!')
        items = event_node.getTag('items', {'node': NS_DEVICE_LIST})
        if items and len(items.getChildren()) == 1:
            account = msg.conn.name
            contact_jid = gajim.get_jid_without_resource(msg.fjid)

            log.debug(account + ' ⇒ Received OMEMO pep for jid ' + contact_jid)

            devices = items.getChildren()[0].getTag('list').getChildren()
            devices_list = [int(dev.getAttr('id')) for dev in devices]

            state = self.omemo_states[account]

            my_jid = gajim.get_jid_from_account(account)

            if contact_jid == my_jid:
                log.debug(state.name + ' ⇒ Received own device_list ' + str(
                    devices_list))
                state.add_own_devices(devices_list)

                if not state.own_device_id_published() or anydup(
                        state.own_devices):
                    # Our own device_id is not in the list, it could be
                    # overwritten by some other client?
                    # also remove duplicates
                    devices_list = list(set(state.own_devices))
                    devices_list.append(state.own_device_id)
                    self.publish_own_devices_list(state)
            else:
                state.add_devices(contact_jid, devices_list)
                if account in self.ui_list and contact_jid in self.ui_list[account]:
		    self.ui_list[account][contact_jid].toggle_omemo(True)
            return True
        return False

    @log_calls('OmemoPlugin')
    def publish_own_devices_list(self, state):
        devices_list = state.own_devices
        devices_list += [state.own_device_id]

        log.debug(state.name + ' ⇒ Publishing own devices_list ' + str(
            devices_list))
        iq = DeviceListAnnouncement(devices_list)
        gajim.connections[state.name].connection.send(iq)
        id_ = str(iq.getAttr('id'))
        iq_ids_to_callbacks[id_] = lambda event: log.debug(event)

    @log_calls('OmemoPlugin')
    def connect_ui(self, chat_control):
        log.info("DRIN")
        account = chat_control.contact.account.name
        jid = chat_control.contact.jid
        if account not in self.ui_list:
            self.ui_list[account] = {}
        self.ui_list[account][jid] = Ui(self, chat_control)

    @log_calls('OmemoPlugin')
    def handle_iq_received(self, event):
        global iq_ids_to_callbacks
        id_ = str(event.stanza.getAttr("id"))
        if id_ in iq_ids_to_callbacks:
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
        to_jid = contact.jid
        my_jid = gajim.get_jid_from_account(account)
        missing_keys = state.find_missing_sessions(to_jid)
        for k in missing_keys:
            self._query_prekey(state, to_jid, k)

        for k in state.find_own_missing_sessions(my_jid):
            self._query_prekey(state, my_jid, k)

    @log_calls('OmemoPlugin')
    def _query_prekey(self, state, jid, key):
        log.debug('Query prekey bundles ⇒ ' + str(key) + 'for: ' + jid)
        iq = BundleInformationQuery(jid, key)
        iq_id = str(iq.getAttr('id'))
        iq_ids_to_callbacks[iq_id] = \
            lambda stanza: self.session_from_prekey_bundle(state,
                                                           stanza,
                                                           jid,
                                                           key)
        gajim.connections[state.name].connection.send(iq)

    @log_calls('OmemoPlugin')
    def session_from_prekey_bundle(self, state, stanza, recipient_id,
                                   device_id):
        bundle_dict = unpack_device_bundle(stanza, device_id)
        if not bundle_dict:
            log.warn('Failed requesting a bundle')
            return

        state.build_session(recipient_id, device_id, bundle_dict)

    @log_calls('OmemoPlugin')
    def publish_bundle(self, account):
        state = self.omemo_states[account.name]
        iq = BundleInformationAnnouncement(state.bundle, state.own_device_id)
        gajim.connections[state.name].connection.send(iq)
        id_ = str(iq.getAttr("id"))
        log.debug(account.name + " → PUBLISHING BUNDLE ")
        iq_ids_to_callbacks[id_] = lambda stanza: \
            self.publish_bundle_result(stanza, state)

    @log_calls('OmemoPlugin')
    def publish_bundle_result(self, stanza, state):
        account = state.name
        state = self.omemo_states[account]
        if successful(stanza):
            log.debug(account + ' → Publishing bundle was successful')
            if not state.own_device_id_published():
                log.debug(account + ' → Device list needs updating')
                self.publish_own_devices_list(state)
            else:
                log.debug(account + ' → Device list up to date')
        else:
            log.debug(account + ' → Publishing bundle was NOT successful')

    @log_calls('OmemoPlugin')
    def clear_device_list(self, contact):
        account = contact.account.name
        state = self.omemo_states[account]
        devices_list = [state.own_device_id]

        log.info(state.name + ' ⇒ Clearing devices_list ' + str(devices_list))
        iq = DeviceListAnnouncement(devices_list)
        gajim.connections[state.name].connection.send(iq)
        id_ = str(iq.getAttr('id'))
        iq_ids_to_callbacks[id_] = lambda event: log.info(event)

    @log_calls('OmemoPlugin')
    def handle_outgoing_msgs(self, event):
        if not event.msg_iq.getTag('body'):
            return
        plaintext = event.msg_iq.getBody().encode('utf8')
        account = event.conn.name
        state = self.omemo_states[account]
        full_jid = str(event.msg_iq.getAttr('to'))
        to_jid = gajim.get_jid_without_resource(full_jid)
        if to_jid not in state.omemo_enabled:
            return False
        try:
            msg_dict = state.create_msg(gajim.get_jid_from_account(account), to_jid, plaintext)
            if not msg_dict:
                return True
            encrypted_node = OmemoMessage(msg_dict)
            event.msg_iq.delChild('body')
            event.msg_iq.addChild(node=encrypted_node)
            log.debug(account + ' → ' + str(event.msg_iq))
        except (NoValidSessions):
            return

    def omemo_enable_for(self, contact):
        account = contact.account.name
        state = self.omemo_states[account]
        state.omemo_enabled |= {contact.jid}

    def omemo_disable_for(self, contact):
        account = contact.account.name
        state = self.omemo_states[account]
        state.omemo_enabled.remove(contact.jid)

    def has_omemo(self, contact):
        account = contact.account.name
        state = self.omemo_states[account]
        if state.device_ids_for(contact):
            return True
        return False


@log_calls('OmemoPlugin')
def anydup(thelist):
    seen = set()
    for x in thelist:
        if x in seen:
            return True
        seen.add(x)
    return False
