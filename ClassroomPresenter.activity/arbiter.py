# arbiter.py
#
# Mediator class that handles (and thus decouples) all inter-class
# communication.
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

# List of signals:
# ----------------
#
# Each signal can be connected to by calling 'arbiter.connect_<signal-name>(<callback-function>)'
# ex: arbiter.connect_shared(self.shared_cb).
#
# 'shared' - emitted when the activity is shared
# 'joined' - emitted when joining a shared activity
# 'lock_button_clicked' - emitted when the navigation lock/unlock button is clicked
#                         (only active if in sharing mode)
# 'deck_download_complete' - emitted when the slide deck has been downloaded
# 'navigation_lock_change' - emitted when the activity was signaled over the network to change
#                            its navigation lock state (with one parameter: locked/unlocked flag)
# 'slide_changed' - 
# 'slide_redraw' - 
# 'remove_path' -
# 'deck_changed' -
# 'local_ink_added' -
# 'remote_ink_added' -
# 'instr_state_propagate' -
# 'lock_state_propagate' -
# 'ink_submitted' -
# 'ink_broadcast' -
# 'update_submissions' -
# 'instructor_ink_cleared' -
# 'instructor_ink_removed' -
# 'undo_redo_changed' - 

import logging
import gobject

class ObjectNotRegisteredError(Exception):
    """ An exception class that is thrown when one object tries to communicate
        with another object through the arbiter, but the target object has not
        been registered with the arbiter.
        NOTE: This is experimental at the moment, not all of Arbiter's methods
              throw this exception if the required object is not registered.   """
    def __init__(self, err):
        self.err = err

    def __str__(self):
        return repr(self.err)

class Arbiter(gobject.GObject):

    def __init__(self, activity):
        gobject.GObject.__init__(self)

        # logging
        self.__logger = logging.getLogger('Arbiter')
        self.__logger.setLevel(logging.DEBUG)

        # vars
        self.__deck = None
        self.__shared = None
        self.__renderer = None
        self.__slide_viewer = None
        self.__text_area = None
        self.__nav_tb = None
        self.__ink_tb = None
        
        self.__logger.debug('Hello from Arbiter.')

        self.__activity = activity
        self.__logger.debug('Activity registered with Arbiter!')

    def register_deck(self, deck):
        self.__deck = deck
        self.__logger.debug('Deck registered with Arbiter!')

    def register_shared(self, shared):
        self.__shared = shared
        self.__logger.debug('Shared registered with Arbiter!')

    def register_renderer(self, renderer):
        self.__renderer = renderer
        self.__logger.debug('Renderer registered with Arbiter!')

    def register_slide_viewer(self, slide_viewer):
        self.__slide_viewer = slide_viewer
        self.__logger.debug('SlideViewer registered with Arbiter!')

    def register_text_area(self, text_area):
        self.__text_area = text_area
        self.__logger.debug('TextArea registered with Arbiter!')

    def register_nav_tb(self, nav_tb):
        self.__nav_tb = nav_tb
        self.__logger.debug('NavToolBar registered with Arbiter!')

    def register_ink_tb(self, ink_tb):
        self.__ink_tb = ink_tb
        self.__logger.debug('InkToolBar registered with Arbiter!')

    # Activity mediation

    def do_read_file(self, file_path):
        self.__activity.read_file(file_path)

    def do_write_file(self, file_path):
        self.__activity.write_file(file_path)

    def get_shared_activity(self):
        return self.__activity.get_shared_activity()

    def connect_shared(self, cb):
        # note: checks to make sure the required object is registered first...all methods
        #       should evnetually do this
        if self.__activity: self.__activity.connect('shared', cb)
        else:               raise ObjectNotRegisteredError('Activity object not registered!')

    def connect_joined(self, cb):
        self.__activity.connect('joined', cb)

    def connect_quitting(self, cb):
        self.__activity.connect('quitting', cb)

    # NavToolBar mediation

    def connect_lock_button_clicked(self, cb):
        self.__nav_tb.connect('lock-button-clicked', cb)

    # Shared mediation

    def get_sharing_mode(self):
        if self.__shared:
            return self.__shared.get_sharing_mode()
        else:
            return True # default to sharer (instructor)

    def get_lock_mode(self):
        if self.__shared:
            return self.__shared.get_lock_mode()
        else:
            return False # default to not locked

    def connect_deck_download_complete(self, cb):
        self.__shared.connect('deck-download-complete', cb)

    def connect_navigation_lock_change(self, cb):
        self.__shared.connect('navigation-lock-change', cb)

    # Deck mediation

    def get_submission_list(self, n=None):
        return self.__deck.get_submission_list(n)

    def get_deck_is_at_beginning(self):
        return self.__deck.is_at_beginning()

    def get_deck_is_at_end(self):
        return self.__deck.is_at_end()

    def get_self_ink_or_submission(self):
        return self.__deck.get_self_ink_or_submission()

    def get_active_submission(self):
        return self.__deck.get_active_submission()

    def get_slide_thumb(self, n=-1):
        return self.__deck.get_slide_thumb(n)

    def get_slide_count(self):
        return self.__deck.get_slide_count()

    def get_slide_index(self):
        return self.__deck.get_slide_index()

    def get_slide_layers(self, n=-1):
        return self.__deck.get_slide_layers(n)

    def get_slide_dimensions_from_xml(self, n=-1):
        return self.__deck.get_slide_dimensions_from_xml(n)

    def get_instructor_ink(self):
        return self.__deck.get_instructor_ink()

    def get_deck_path(self):
        return self.__deck.get_deck_path()

    def do_set_active_submission(self, sub):
        self.__deck.set_active_submission(sub)

    def do_set_slide_thumb(self, filename, n=-1):
        self.__deck.set_slide_thumb(filename, n)

    def do_set_slide_text(self, textval):
        self.__deck.set_slide_text(textval)

    def do_next_slide(self):
        self.__deck.next_slide()

    def do_previous_slide(self):
        self.__deck.previous_slide()

    def do_goto_slide(self, n, local_request):
        self.__deck.goto_slide(n, local_request)

    def do_reload_deck(self):
        self.__deck.reload()

    def do_clear_instructor_ink(self, n=None):
        self.__deck.clear_instructor_ink(n)

    def do_add_submission(self, whofrom, inks, text="", n=None):
        self.__deck.add_submission(whofrom, inks, text="", n=None)

    def do_submit_ink(self):
        self.__deck.submit_ink()

    def do_broadcast_ink(self):
        self.__deck.broadcast_ink()

    def do_add_ink_to_slide(self, pathstr, local_request, n=None):
        self.__deck.add_ink_to_slide(pathstr, local_request, n=None)

    def do_remove_instructor_path_by_uid(self, uid, n=None):
        self.__Deck.remove_instructor_path_by_uid(uid, n)

    def do_remove_local_path_by_uid(self, uid, n=None):
        self.__Deck.remove_local_path_by_uid(uid, n)

    def do_deck_save(self):
        self.__deck.save()

    def connect_slide_changed(self, cb):
        self.__deck.connect('slide-changed', cb)

    def connect_slide_redraw(self, cb):
        self.__deck.connect('slide-redraw', cb)
    
    def connect_remove_path(self, cb):
        self.__deck.connect('remove-path', cb)

    def connect_deck_changed(self, cb):
        self.__deck.connect('deck-changed', cb)

    def connect_local_ink_added(self, cb):
        self.__deck.connect('local-ink-added', cb)

    def connect_remote_ink_added(self, cb):
        self.__deck.connect('remote-ink-added', cb)

    def connect_instr_state_propagate(self, cb):
        self.__deck.connect('instr-state-propagate', cb)

    def connect_lock_state_propagate(self, cb):
        self.__deck.connect('lock-state-propagate', cb)

    def connect_ink_submitted(self, cb):
        self.__deck.connect('ink-submitted', cb)

    def connect_ink_broadcast(self, cb):
        self.__deck.connect('ink-broadcast', cb)

    def connect_update_submissions(self, cb):
        self.__deck.connect('update-submissions', cb)

    def connect_instructor_ink_cleared(self, cb):
        self.__deck.connect('instructor-ink-cleared', cb)

    def connect_instructor_ink_removed(self, cb):
        self.__deck.connect('instructor-ink-removed', cb)

    # SlideViewer & Deck mediation

    def do_clear_ink(self, n=None):
        self.__slide_viewer.clear_ink()
        self.__deck.clear_ink(n)

    # SlideViewer mediation

    def get_can_undo_redo(self):
        return self.__slide_viewer.can_undo_redo()

    def get_pen_color(self):
        return self.__slide_viewer.get_color()

    def get_pen_size(self):
        return self.__slide_viewer.get_pen()

    def do_set_pen(self, size):
        self.__slide_viewer.set_pen(size)

    def do_set_color(self, r, g, b):
        self.__slide_viewer.set_color(r, g, b)
    
    def do_set_eraser(self):
        self.__slide_viewer.set_eraser()

    def do_undo(self):
        self.__slide_viewer.undo()

    def do_redo(self):
        self.__slide_viewer.redo()

    def connect_undo_redo_changed(self, cb):
        self.__slide_viewer.connect('undo-redo-changed', cb)

    # Renderer mediation

    def do_render_slide_to_surface(self, surface, n=None):
        self.__renderer.render_slide_to_surface(surface, n)

gobject.type_register(Arbiter)
