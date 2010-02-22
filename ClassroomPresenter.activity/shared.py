# shared.py
#
# Top-level class responsible for making Classroom Presenter a shared activity.
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
import os
import gobject

import telepathy
import telepathy.client

import dbus
from dbus.service import method, signal
from dbus.gobject_service import ExportedGObject

from sugar.presence import presenceservice
from sugar.presence.tubeconn import TubeConnection

import utils
from sharedslides import SharedSlides

SERVICE = "edu.washington.cs.ClassroomPresenterXO"
IFACE = SERVICE
PATH = "/edu/washington/cs/ClassroomPresenterXO"

class Shared(ExportedGObject):

    __gsignals__ = {
        'navigation-lock-change' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_BOOLEAN,)),
        'deck-download-complete' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        }
        
    def __init__(self, arbiter, work_path):
        gobject.GObject.__init__(self)

        self.__arbiter = arbiter

        self.__logger = logging.getLogger('Shared')
        self.__logger.setLevel(logging.DEBUG)

        self.__sharing = False
        self.__shared_slides = None
        self.__got_dbus_tube = False
        self.__locked = False
        self.__pservice = presenceservice.get_instance()
        #self.__owner = self.__pservice.get_owner()

        self.__cpxo_path = os.path.join(work_path, 'deck.cpxo')

        self.__arbiter.connect_shared(self.shared_cb)
        self.__arbiter.connect_joined(self.joined_cb)

        self.__logger.debug('Hello from Shared. Waiting to become sharer or joiner.')

    def get_is_instructor(self):
        """ Returns a flag that indicates whether we shared the activity.
            Also called 'instructor mode'. """
        return self.__sharing

    def get_lock_mode(self):
        """ Returns a flag that indicates whether student navigation is locked. """
        return self.__locked

    def shared_cb(self, activity):
        """ Called when the activity is shared """
        self.__logger.debug('The activity has been shared.')
        self.__sharing = True
        self.__arbiter.do_write_file(self.__cpxo_path)

        # connect to local instructor signals
        self.__arbiter.connect_quitting(self.activity_quit_cb)
        self.__arbiter.connect_slide_changed(self.send_slide_changed_signal_cb)
        self.__arbiter.connect_local_ink_added(self.send_ink_path_cb)
        self.__arbiter.connect_instructor_ink_cleared(self.instr_clear_ink_cb)
        self.__arbiter.connect_instructor_ink_removed(self.instr_remove_ink_cb)
        self.__arbiter.connect_ink_broadcast(self.bcast_submission_cb)
        self.__arbiter.connect_lock_button_clicked(self.lock_mode_switch)

        self.shared_setup()

    def joined_cb(self, activity):
        """ Called when the activity is joined """
        self.__logger.debug('Joined another activity.')
        self.__sharing = False
        # for showing slide deck download progress
        activity.do_progress_view()
        activity.set_progress(0.0)

        # connect to local student signals
        self.__arbiter.connect_ink_submitted(self.submit_ink_cb)

        self.shared_setup()

    def shared_setup(self):
        """ Called by joined_cb and shared_cb because all of this needs to happen
            whether we are sharing or joining the activity """

        self.__shared_activity = self.__arbiter.get_shared_activity()

        if self.__shared_activity is None:
            self.__logger.error('Failed to share or join activity!')
            return

        self.__tubes_chan = self.__shared_activity.telepathy_tubes_chan
        self.__iface = self.__tubes_chan[telepathy.CHANNEL_TYPE_TUBES]

        self.__text_chan = self.__shared_activity.telepathy_text_chan
        self.__iface_grp = self.__text_chan[telepathy.CHANNEL_INTERFACE_GROUP]

        self.__conn = self.__shared_activity.telepathy_conn
        self.__my_handle = self.__conn.GetSelfHandle()

        #self.__shared_activity.connect('buddy-joined', self.buddy_joined_cb)
        #self.__shared_activity.connect('buddy-left', self.buddy_left_cb)

        # takes care of downloading (and then sharing) the slide deck over stream tubes
        self.__shared_slides = SharedSlides(self.__sharing, self.__cpxo_path,
                                            self.__shared_activity, self.__arbiter.do_read_file)
        self.__shared_slides.connect('deck-download-complete', self.deck_download_complete_cb)

        # now for the dbus tube
        self.__iface.connect_to_signal('NewTube', self.new_tube_cb)

        if (self.__sharing):
            self.__logger.debug("We are sharing, making a dbus tube and setting locked nav mode.")
            self.lock_nav()
            id = self.__iface.OfferDBusTube(SERVICE, {})
        else:
            self.__logger.debug("We are joining, looking for the global dbus tube.")
            self.__iface.ListTubes( reply_handler=self.list_tubes_reply_cb,
                                    error_handler=self.list_tubes_error_cb )

    def lock_mode_switch(self, widget=None):
        """ Switches the lock mode from locked to unlocked and vice versa """
        # first switch our own lock mode
        if (self.__locked):
            self.unlock_nav()
        else:
            self.lock_nav()
    
        # if we are instructor, tell student XOs to go into our new lock mode
        if (self.__sharing):
            self.Lock_Nav(self.__locked)
            
    def lock_nav(self):
        self.__logger.debug("Locking navigation.")
        self.__locked = True
        # if we are the instructor, force students to jump to our slide
        if self.__got_dbus_tube and self.__sharing:
            self.Slide_Changed(self.__arbiter.get_slide_index())
        self.emit('navigation-lock-change', self.__locked)

    def unlock_nav(self):
        self.__logger.debug("Unlocking navigation.")
        self.__locked = False
        self.emit('navigation-lock-change', self.__locked)


    def deck_download_complete_cb(self, object):
        """ Catches the deck_download_complete signal from SharedSlides and sends a local
            and dbus signal. """
        self.__logger.debug("Deck download is complete, sending Deck_Download_Complete dbus signal.")
        self.Deck_Download_Complete()
        self.emit('deck-download-complete')

    def student_dl_complete_cb(self, sender):
        """ Catches the Deck_Download_Complete dbus signal from students, lets us know that they
            are ready to have initial state information pushed onto them """
        self.__logger.debug("Got Deck_Download_Complete dbus signal, pushing initial state info to student.")
        proxy_object = self.__dbus_tube.get_object(sender, PATH)
        proxy_object.Push_Initial_State(self.__locked, self.__arbiter.get_slide_index(),
                                        dbus_interface=IFACE)
        
    def list_tubes_reply_cb(self, tubes):
        for tube_info in tubes:
            self.new_tube_cb(*tube_info)

    def list_tubes_error_cb(self, e):
        self.__logger.error('ListTubes() failed: %s', e)

    def new_tube_cb(self, tube_id, initiator, type, service, params, state):
        self.__logger.debug('New tube: ID=%d initator=%d type=%d service=%s params=%r state=%d',
                            tube_id, initiator, type, service, params, state)
        if (not self.__got_dbus_tube and type == telepathy.TUBE_TYPE_DBUS and service == SERVICE):
            if( state == telepathy.TUBE_STATE_LOCAL_PENDING):
                self.__iface.AcceptDBusTube(tube_id)

            self.__dbus_tube = TubeConnection(self.__conn, self.__iface, tube_id,
                                              group_iface=self.__iface_grp)
            self.__got_dbus_tube = True
            self.__logger.debug("Got our dbus tube!")

            # lots of stuff to do once we get our tube
            if (self.__sharing):
                # connect to dbus signals sent by students:
                self.__dbus_tube.add_signal_receiver(self.student_dl_complete_cb, 'Deck_Download_Complete',
                                                     IFACE, path=PATH, sender_keyword='sender')
                self.__dbus_tube.add_signal_receiver(self.receive_submission_cb, 'Send_Submission',
                                                     IFACE, path=PATH)
            else:
                # connect to dbus signals sent by instructor
                self.__dbus_tube.add_signal_receiver(self.slide_changed_cb, 'Slide_Changed',
                                                     IFACE, path=PATH)
                self.__dbus_tube.add_signal_receiver(self.lock_nav_cb, 'Lock_Nav',
                                                     IFACE, path=PATH)
                self.__dbus_tube.add_signal_receiver(self.add_ink_path_cb, 'Add_Ink_Path',
                                                     IFACE, path=PATH)
                self.__dbus_tube.add_signal_receiver(self.recv_instr_clear_ink_cb, 'Instructor_Clear_Ink',
                                                     IFACE, path=PATH)
                self.__dbus_tube.add_signal_receiver(self.recv_instr_remove_ink_cb, 'Instructor_Remove_Ink',
                                                     IFACE, path=PATH)
                self.__dbus_tube.add_signal_receiver(self.receive_submission_cb, 'Bcast_Submission',
                                                     IFACE, path=PATH)

            #self.__dbus_tube.watch_participants(self.participant_change_cb)

            super(Shared, self).__init__(self.__dbus_tube, PATH)


    # --- BEGIN Instructor CallBacks ---

    # UNUSED
    def participant_change_cb(self, added, removed):
        """ Callback on instructor XO for when someone joins or leaves the tube """
        for handle, bus_name in added:
            buddy = self._get_buddy(handle)
            if buddy is not None:
                if handle != self.__my_handle and self.__sharing:
                    self.__logger.debug("New student joined: %s", buddy.props.nick)

        for handle in removed:
            buddy = self._get_buddy(handle)
            if buddy is not None:
                self.__logger.debug('Buddy %s was removed' % buddy.props.nick)

    def activity_quit_cb(self, widget):
        """ Called when the activity is quit. """
        self.__logger.debug("Activity is quitting. Making sure student navigation is unlocked.")
        if self.__locked:
            self.lock_mode_switch()

    def send_slide_changed_signal_cb(self, widget):
        """ Arbitrates the sending of the Slide_Changed signal """
        self.__logger.debug("Got the slide-changed signal.")
        if self.__locked:
            self.__logger.debug("Navigation is locked, sending Slide_Changed to students.")
            self.Slide_Changed(self.__arbiter.get_slide_index())

    def send_ink_path_cb(self, widget, inkstr):
        self.__logger.debug("send_ink_path_cb called")
        if (self.__sharing and self.__got_dbus_tube):
            self.Add_Ink_Path(self.__arbiter.get_slide_index(), inkstr)
    
    def receive_submission_cb(self, sender, slide_idx, inks, text):
        self.__logger.debug("Received submission from '%s'.", sender)
        self.__arbiter.do_add_submission(sender, inks, text, slide_idx)
        
    def bcast_submission_cb(self, widget, whofrom, inks, text):
        if self.__sharing and self.__got_dbus_tube:
            cur_idx = self.__arbiter.get_slide_index()
            self.Bcast_Submission(whofrom, cur_idx, inks, text)
    
    def instr_clear_ink_cb(self, widget, idx):
        if self.__sharing and self.__got_dbus_tube:
            self.Instructor_Clear_Ink(idx)

    def instr_remove_ink_cb(self, widget, uid, idx):
        if self.__sharing and self.__got_dbus_tube:
            self.Instructor_Remove_Ink(uid, idx)

    # --- END Instructor CallBacks ---


    # --- BEGIN Instructor DBus Signals/Methods ---

    @signal(dbus_interface=IFACE, signature='uu')
    def Instructor_Remove_Ink(self, uid, idx):
        pass
    
    @signal(dbus_interface=IFACE, signature='u')
    def Instructor_Clear_Ink(self, idx):
        pass
    
    @signal(dbus_interface=IFACE, signature='u')
    def Slide_Changed(self, slide_num):
        """ Signals joiners to move to given slide """
        self.__logger.debug("Sending the Slide_Changed signal with slide num %d.", slide_num)
        pass

    @signal(dbus_interface=IFACE, signature='u')
    def Lock_Nav(self, lock):
        """ Signals joiners to lock or unlock navigation """
        self.__logger.debug("Sending Lock_Nav signal with bool %u", lock)
        pass

    @signal(dbus_interface=IFACE, signature='us')
    def Add_Ink_Path(self, slide_idx, pathstr):
        self.__logger.debug("Sending new ink path")
        pass

    @signal(dbus_interface=IFACE, signature='suss')
    def Bcast_Submission(self, sender, slide_idx, inks, text):
        pass    

    # --- END Instructor DBus Signals/Methods ---


    # --- BEGIN Student CallBacks ---

    def recv_instr_remove_ink_cb(self, uid, idx):
        self.__arbiter.do_remove_instructor_path_by_uid(uid, idx)

    def recv_instr_clear_ink_cb(self, idx):
        self.__arbiter.do_clear_instructor_ink(idx)

    def slide_changed_cb(self, slide_idx):
        """ Called on the joiners when they receive the Slide_Changed dbus signal """
        self.__logger.debug("Received the Slide_Changed signal and changing to slide %d.",
                            slide_idx)

        self.__arbiter.do_goto_slide(slide_idx, local_request=False)

    def lock_nav_cb(self, lock):
        """ Called on joiners when they receive the Lock_Nav dbus signal """
        self.__logger.debug("Received the Lock_Nav signal with bool %u", lock)
        if (lock):
            self.lock_nav()
        else:
            self.unlock_nav()

    def add_ink_path_cb(self, idx, inkstr):
        self.__logger.debug("Received new ink path")
        self.__arbiter.do_add_ink_to_slide(inkstr, local_request=False, n=idx)

    def submit_ink_cb(self, widget, inks, text):
        if not self.__sharing and self.__got_dbus_tube:
            cur_idx = self.__arbiter.get_slide_index()
            my_csh = self.__iface_grp.GetSelfHandle()
            buddy = self._get_buddy(my_csh)

            if buddy is not None:
                sender = buddy.props.nick
            else:
                sender = 'Unknown'

            self.__logger.debug("Sending submission: idx '%d', sender '%s'.", cur_idx, sender)
            self.Send_Submission(sender, cur_idx, inks, text)
    
    # --- END Student CallBacks ---


    # --- BEGIN Student DBus Signals/Methods ---

    @signal(dbus_interface=IFACE, signature='')
    def Deck_Download_Complete(self):
        """ Signal from the student informing instructor that the deck download has finished """
        self.__logger.debug("Sending Deck_Download_Complete signal, ready for initial state info.")
        pass

    @signal(dbus_interface=IFACE, signature='suss')
    def Send_Submission(self, sender, slide_idx, inks, text):
        pass
    
    @method(dbus_interface=IFACE, in_signature='uu', out_signature='')
    def Push_Initial_State(self, locked, slide_idx):
        """ Called on student XO to push initial state info """
        self.__logger.debug("Got initial state data from instructor: locked? %u, slide? %u",
                            locked, slide_idx)

        self.__arbiter.do_goto_slide(slide_idx, local_request=False)

        if locked:
            self.lock_nav()
        else:
            self.unlock_nav()

    # --- END Student DBus Signals/Methods ---


    # BEGIN Private Methods

    def _get_buddy(self, cs_handle):
        """Get a Buddy from a channel specific handle."""
        self.__logger.debug('Trying to find owner of handle %u...', cs_handle)
        my_csh = self.__iface_grp.GetSelfHandle()
        self.__logger.debug('My handle in that group is %u', my_csh)
        if my_csh == cs_handle:
            handle = self.__conn.GetSelfHandle()
            self.__logger.debug('CS handle %u belongs to me, %u', cs_handle, handle)
        elif group.GetGroupFlags() & telepathy.CHANNEL_GROUP_FLAG_CHANNEL_SPECIFIC_HANDLES:
            handle = group.GetHandleOwners([cs_handle])[0]
            self.__logger.debug('CS handle %u belongs to %u', cs_handle, handle)
        else:
            handle = cs_handle
            self.__logger.debug('non-CS handle %u belongs to itself', handle)
            # XXX: deal with failure to get the handle owner
            assert handle != 0
        return self.__pservice.get_buddy_by_telepathy_handle(
            self.__conn.service_name, self.__conn.object_path, handle)

    # END Private Methods


    # DEPRECATED
    def buddy_joined_cb(self, activity, buddy):
        """ Called when a buddy joins the activity """
        if self.__sharing is True:
            utils.run_dialog("Instructor", buddy.props.nick + " has joined!")

    # DEPRECATED
    def buddy_left_cb(self, activity, buddy):
        """ Called when a buddy leaves the activity """
        if self.__sharing is True:
            utils.run_dialog("Instructor", buddy.props.nick + " has left!")

gobject.type_register(Shared)
