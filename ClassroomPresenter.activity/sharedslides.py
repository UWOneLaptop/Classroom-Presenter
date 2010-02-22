# sharedslides.py
#
# Class that performs all work relating to the sharing of slide decks and ink.
# Kris Plunkett <kp86@cs.washington.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import logging

import sys
import os
import time
import random
import gobject

import telepathy
import telepathy.client

import dbus
from dbus.service import method, signal
from dbus.gobject_service import ExportedGObject

from sugar.presence import presenceservice
from sugar import network
from sugar.presence.tubeconn import TubeConnection

SERVICE = "edu.washington.cs.ClassroomPresenterXO"
IFACE = SERVICE
PATH = "/edu/washington/cs/ClassroomPresenterXO"


# Define a simple HTTP server for sharing data.
class ReadHTTPRequestHandler(network.ChunkedGlibHTTPRequestHandler):
    def translate_path(self, path):
        return self.server._filepath
 
class ReadHTTPServer(network.GlibTCPServer):
    def __init__(self, server_address, filepath):
        self._filepath = filepath
        network.GlibTCPServer.__init__(self, server_address, ReadHTTPRequestHandler)


class SharedSlides(gobject.GObject):
    """ Handles all sharing of slides and ink """

    __gsignals__ = {
        'deck-download-complete' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        }

    def __init__(self, init, cpxo_path, shared_activity, read_file_cb):
        gobject.GObject.__init__(self)

        self.__sharing_mode = init
        self.__cpxo_path = cpxo_path
        self.__shared_activity = shared_activity
        self.read_file_cb = read_file_cb

        self.__logger = logging.getLogger('SharedSlides')
        self.__logger.setLevel(logging.DEBUG)

        self.__tubes_chan = self.__shared_activity.telepathy_tubes_chan
        self.__iface = self.__tubes_chan[telepathy.CHANNEL_TYPE_TUBES]

        if (self.__sharing_mode):
            # we shared the activity, so make the deck available for download
            self.__logger.debug('Hello from SharedSlides (sharer).')
            self.__have_deck = True
            self.share_deck()
        else:
            # find a stream tube to download the slide deck from
            self.__logger.debug('Hello from SharedSlides (joiner).')
            self.__iface.connect_to_signal('NewTube', self.new_tube_cb)
            self.__have_deck = False
            self.get_stream_tube()

    def get_stream_tube(self):
        """ Attempts to download the slide deck from an available stream tube """
        self.__iface.ListTubes(
            reply_handler=self.list_tubes_reply_cb,
            error_handler=self.list_tubes_error_cb)

    def handle_download_fail(self):
        """ If an attempt to download the deck fails, this method takes care of it """
        self.__logger.error('Download failed! Sleeping five seconds and trying again.')
        time.sleep(5)
        self.get_stream_tube()
        
    def list_tubes_reply_cb(self, tubes):
        for tube_info in tubes:
            self.new_tube_cb(*tube_info)

    def list_tubes_error_cb(self, e):
        self.__logger.error('ListTubes() failed: %s', e)
        self.handle_download_fail

    def new_tube_cb(self, id, initiator, type, service, params, state):
        self.__logger.debug('New tube: ID=%d initiator=%d type=%d service=%s params=%r state=%d',
                            id, initiator, type, service, params, state)
        
        if (not self.__have_deck and
            type == telepathy.TUBE_TYPE_STREAM and
            service == SERVICE and
            state == telepathy.TUBE_STATE_LOCAL_PENDING):
            addr = self.__iface.AcceptStreamTube(id,
                                                 telepathy.SOCKET_ADDRESS_TYPE_IPV4,
                                                 telepathy.SOCKET_ACCESS_CONTROL_LOCALHOST, 0,
                                                 utf8_strings=True)
            self.__logger.debug("Got a stream tube!")
            
            # sanity checks
            assert isinstance(addr, dbus.Struct)
            assert len(addr) == 2
            assert isinstance(addr[0], str)
            assert isinstance(addr[1], (int, long))
            assert addr[1] > 0 and addr[1] < 65536
            ip_addr = addr[0]
            port = int(addr[1])

            self.__logger.debug("The stream tube is good!")
            self.download_file(ip_addr, port, id)
            
    def download_file(self, ip_addr, port, tube_id):
        """ Performs the actual download of the slide deck """
        self.__logger.debug("Downloading from ip %s and port %d.", ip_addr, port)

        getter = network.GlibURLDownloader("http://%s:%d/document" % (ip_addr, port))
        getter.connect("finished", self.download_result_cb, tube_id)
        getter.connect("progress", self.download_progress_cb, tube_id)
        getter.connect("error", self.download_error_cb, tube_id)
        self.__logger.debug("Starting download to %s...", self.__cpxo_path)
        getter.start(self.__cpxo_path)

    def download_result_cb(self, getter, tempfile, suggested_name, tube_id):
        """ Called when the file download was successful """
        self.__logger.debug("Got file %s (%s) from tube %u",
                            tempfile, suggested_name, tube_id)
        self.emit('deck-download-complete')
        self.read_file_cb(self.__cpxo_path)

    def download_progress_cb(self, getter, bytes_downloaded, tube_id):
        tmp = True
        #self.__logger.debug("Bytes downloaded from tube %u: %u", tube_id, bytes_downloaded)

    def download_error_cb(self, getter, err, tube_id):
        self.__logger.error('Download failed on tube %u: %s', tube_id, err)
        self.handle_download_fail()

    def share_deck(self):
        """ As the instructor XO, or as a student that has completed the deck download
        share the deck with others in the activity """

        # get a somewhat random port number
        self.__port = random.randint(1024, 65535)
        self.__ip_addr = "127.0.0.1"
        
        self._fileserver = ReadHTTPServer(("", self.__port), self.__cpxo_path)
        self.__logger.debug('Started an HTTP server on port %d', self.__port)

        self.__iface.OfferStreamTube(SERVICE, {},
                                     telepathy.SOCKET_ADDRESS_TYPE_IPV4,
                                     (self.__ip_addr, dbus.UInt16(self.__port)),
                                     telepathy.SOCKET_ACCESS_CONTROL_LOCALHOST, 0)
        self.__logger.debug('Made a stream tube.')

gobject.type_register(SharedSlides)
