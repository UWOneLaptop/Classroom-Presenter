# toolbars.py
#
# Classes defining toolbars for Classroom Presenter
# B. Mayton <bmayton@cs.washington.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301     USA


from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.menuitem import MenuItem
from gettext import gettext as _

import gtk
import gobject
import pango
import logging
import threading

class NavToolBar(gtk.Toolbar):

    __gsignals__ = {
        'lock-button-clicked' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
        }
    
    def __init__(self, arbiter):
        gtk.Toolbar.__init__(self)
    
        self.__arbiter = arbiter

        self.__logger = logging.getLogger('Navigation Toolbar')
        self.__logger.setLevel(logging.DEBUG)

        self.__prevbtn = ToolButton('go-previous')
        self.__prevbtn.set_tooltip(_("Previous slide"))
        self.__prevbtn.connect('clicked', self.previous_btn_clicked)
        
        self.__nextbtn = ToolButton('go-next')
        self.__nextbtn.set_tooltip(_("Next slide"))
        self.__nextbtn.connect('clicked', self.next_btn_clicked)
        
        # page number widget and navigation
        self.__num_page_item = gtk.ToolItem()
        self.__num_current_page = 1
        
        self.__num_page_entry = gtk.Entry()
        self.__num_page_entry.set_text(str(self.__num_current_page))
        self.__num_page_entry.set_alignment(1)
        self.__num_page_entry.connect('activate', self.num_page_activate)
        
        self.__num_page_entry.set_width_chars(4)

        self.__num_page_item.add(self.__num_page_entry)
        self.__num_page_entry.show()
        
        # total page number widget
        self.__total_page_item = gtk.ToolItem()
        self.__total_page_label = gtk.Label()
        
        label_attributes = pango.AttrList()
        label_attributes.insert(pango.AttrSize(14000, 0, -1))
        label_attributes.insert(pango.AttrForeground(65535, 65535, 65535, 0, -1))
        self.__total_page_label.set_attributes(label_attributes)

        self.__total_page_label.set_text(' / ' + str(self.__arbiter.get_slide_count()))
        self.__total_page_item.add(self.__total_page_label)
        self.__total_page_label.show()

        # Instructor/Student mode label
        self.__mode_item = gtk.ToolItem()
        self.__mode_label = gtk.Label()
        
        label_attributes = pango.AttrList()
        label_attributes.insert(pango.AttrSize(14000, 0, -1))
        label_attributes.insert(pango.AttrForeground(65535, 65535, 65535, 0, -1))
        self.__mode_label.set_attributes(label_attributes)

        self.__mode_label.set_text(_("Not Connected"))
        self.__mode_item.add(self.__mode_label)
        self.__mode_label.show()

        # separator between navigation buttons and mode label
        self.__separator1 = gtk.SeparatorToolItem()
        self.__separator1.set_draw(True)
        self.__separator1.set_expand(True)

        # separator between mode label and lock button
        self.__separator2 = gtk.SeparatorToolItem()
        self.__separator2.set_draw(True)
        self.__separator2.set_expand(True)

        # unlocked button
        self.__unlockBtn = ToolButton('unlocked')
        self.__unlockBtn.set_tooltip(_("Student Navigation Unlocked"))

        # navigation is unlocked by default, so insert the unlock button
        
        # locked button
        self.__lockBtn = ToolButton('locked')
        self.__lockBtn.set_tooltip(_("Student Navigation Locked"))

        self.__logger.debug("Connecting to navigation locking and activity sharing signals.")
        self.__arbiter.connect_shared(self.activity_shared_cb)
        self.__arbiter.connect_joined(self.activity_joined_cb)
        self.__arbiter.connect_navigation_lock_change(self.set_lock_button)
        
        # triggers for when slides are changed
        self.__arbiter.connect_slide_changed(self.slide_changed_cb)
        self.__arbiter.connect_deck_changed(self.slide_changed_cb)
        self.slide_changed_cb()

        self.insert(self.__prevbtn, -1)
        self.insert(self.__nextbtn, -1)
        self.insert(self.__num_page_item, -1)
        self.insert(self.__total_page_item, -1)
        self.insert(self.__separator1, -1)
        self.insert(self.__mode_item, -1)
        self.insert(self.__separator2, -1)
        self.insert(self.__unlockBtn, -1)

        self.__prevbtn.show()
        self.__nextbtn.show()
        self.__num_page_item.show()
        self.__total_page_item.show()
        self.__separator1.show()
        self.__mode_item.show()
        self.__separator2.show()
        self.__unlockBtn.show()

        self.show() # show the entire toolbar
        
    def activity_shared_cb(self, widget):
        #Callback for when the activity is shared
        # bind the lock button click with switching lock mode
        self.__lockBtn.connect('clicked', self.lock_btn_cb)
        self.__unlockBtn.connect('clicked', self.lock_btn_cb)
        self.__mode_label.set_text(_("Instructor"))

    def activity_joined_cb(self, widget):
        """ Callback for when the activity is joined """
        self.__mode_label.set_text(_("Student"))
        self.__lockBtn.set_sensitive(False)
        self.__unlockBtn.set_sensitive(False)

    def lock_btn_cb(self, widget):
        """ The lock/unlock button has been clicked. """
        self.emit('lock-button-clicked')

    def set_lock_button(self, widget, is_locked):
        sharing = self.__arbiter.get_is_instructor()
        
        self.__logger.debug("Changing lock button, lock mode %u, init %u",
                    is_locked, sharing)
        if is_locked:
            new_button = self.__lockBtn
            if not sharing:
                self.__prevbtn.set_sensitive(False)
                self.__nextbtn.set_sensitive(False)
        else:
            new_button = self.__unlockBtn
            if not sharing:
                self.__prevbtn.set_sensitive(True)
                self.__nextbtn.set_sensitive(True)
        
        old = self.get_nth_item(7)
        self.remove(old)
        self.insert(new_button, 7)
        new_button.show()
        self.queue_draw()
        
    def next_btn_clicked(self, widget):
        self.__arbiter.do_next_slide()
            
    def previous_btn_clicked(self, widget):
        self.__arbiter.do_previous_slide()
        
    def slide_changed_cb(self, widget=None):
        self.__logger.debug("Changing slides!")
        if self.__arbiter.get_deck_is_at_beginning():
            self.__prevbtn.set_sensitive(False)
        else:
            self.__prevbtn.set_sensitive(True)
        if self.__arbiter.get_deck_is_at_end():
            self.__nextbtn.set_sensitive(False)
        else:
            self.__nextbtn.set_sensitive(True)
        
        self.__num_current_page = self.__arbiter.get_slide_index()
        self.__num_page_entry.set_text(str(self.__num_current_page + 1))
        self.__total_page_label.set_text(' / ' + str(self.__arbiter.get_slide_count()))
        
    def num_page_activate(self, entry):
        page_entered = int(entry.get_text())

        if page_entered < 1:
            page_entered = 1
        elif self.__arbiter.get_slide_count() < page_entered:
            page_entered = self.__arbiter.get_slide_count()

        self.__arbiter.do_goto_slide(page_entered - 1, local_request=True)


class InkToolBar(gtk.Toolbar):

    # Constructor
    def __init__(self, arbiter):
        gtk.Toolbar.__init__(self)
        
        self.__arbiter = arbiter

        self.__logger = logging.getLogger('InkToolBar')
        self.__logger.setLevel(logging.DEBUG)

        self.__cur_color = self.__arbiter.get_pen_color()
        self.__cur_color_str = "blue"
        self.__cur_pen = self.__arbiter.get_pen_size()
        self.__arbiter.connect_slide_redraw(self.update_buttons)
        self.__arbiter.connect_undo_redo_changed(self.update_buttons)
                
        # Red Ink
        self.__red = gtk.RadioToolButton()
        self.__red.set_icon_name('red-button')
        self.insert(self.__red, -1)
        self.__red.show()
        #self.__red.set_tooltip('Red Ink')
        self.__red.connect('clicked', self.set_ink_color, 1.0, 0.0, 0.0, "red")

        # Green Ink
        self.__green = gtk.RadioToolButton(group=self.__red)
        self.__green.set_icon_name('green-button')
        self.insert(self.__green, -1)
        self.__green.show()
        #self.__green.set_tooltip('Green Ink')
        self.__green.connect('clicked', self.set_ink_color, 0.0, 1.0, 0.0, "green")

        # Blue Ink
        self.__blue = gtk.RadioToolButton(group=self.__red)
        self.__blue.set_icon_name('blue-button')
        self.insert(self.__blue, -1)
        self.__blue.show()
        #self.__blue.set_tooltip('Blue Ink')
        self.__blue.connect('clicked', self.set_ink_color, 0.0, 0.0, 1.0, "blue")
        
        # Black Ink
        self.__black = gtk.RadioToolButton(group=self.__red)
        self.__black.set_icon_name('black-button')
        self.insert(self.__black, -1)
        self.__black.show()
        #self.__black.set_tooltip('Black Ink')
        self.__black.connect('clicked', self.set_ink_color, 0.0, 0.0, 0.0, "black")
                
        # Separate ink from untensils
        separator = gtk.SeparatorToolItem()
        separator.set_draw(False)
        self.insert(separator, -1)
        separator.show()

        # Pencil
        self.__pencil = gtk.RadioToolButton()
        self.__pencil.set_icon_name('tool-pencil')
        self.insert(self.__pencil, -1)
        self.__pencil.show()
        #self.__pencil.set_tooltip('Pencil')
        self.__pencil.connect('clicked', self.set_cur_pen, 4)
        
        # Brush
        self.__brush = gtk.RadioToolButton(self.__pencil)
        self.__brush.set_icon_name('tool-brush')
        self.insert(self.__brush, -1)
        self.__brush.show()
        #self.__brush.set_tooltip('Brush')
        self.__brush.connect('clicked', self.set_cur_pen, 8)

        # Erase 
        self.__erase = ToolButton('tool-eraser')
        self.insert(self.__erase, -1)
        self.__erase.show()
        self.__erase.set_tooltip(_('Erase All Ink'))
        self.__erase.connect('clicked', self.erase_btn_clicked)
        
        """
        # Text
        self.__text = ToolButton('text')
        self.insert(self.__text, -1)
        self.__text.show()
        self.__text.set_tooltip('Text')
        """
        
        # Separate tools from text
        separator = gtk.SeparatorToolItem()
        separator.set_draw(False)
        self.insert(separator, -1)
        separator.show()
        
        # Undo
        self.__undo = ToolButton('edit-undo')
        self.insert(self.__undo, -1)
        self.__undo.show()
        self.__undo.set_tooltip(_('Undo'))
        self.__undo.connect('clicked', self.undo)
        
        # Redo
        self.__redo = ToolButton('edit-redo')
        self.insert(self.__redo, -1)
        self.__redo.show()
        self.__redo.set_tooltip(_('Redo'))
        self.__redo.connect('clicked', self.redo)
        
        separator = gtk.SeparatorToolItem()
        separator.set_draw(False)
        separator.set_expand(True)
        self.insert(separator, -1)
        separator.show()
        
        self.__submit = ToolButton('broadcast')
        self.insert(self.__submit, -1)
        self.__submit.show()
        self.__submit.set_tooltip(_('Broadcast Submission'))
        self.__submit.connect('clicked', self.submit_ink_cb)
        
        self.__arbiter.connect_joined(self.activity_joined_cb)

        self.set_tool_buttons()
        self.show()
        self.update_buttons()
    
    def activity_joined_cb(self, widget):
        self.__submit.set_tooltip(_('Submit Ink'))
        self.__submit.set_icon('dialog-ok')
    
    def set_cur_pen(self, widget, size):
        self.__arbiter.do_set_pen(size)

    def set_ink_color(self, widget, r, g, b, color):    
        self.__arbiter.do_set_color(r, g, b)

    def erase_btn_clicked(self, widget):
        self.__arbiter.do_clear_ink()
        
    def set_tool_buttons(self):    
        if self.__cur_color == (1.0, 0.0, 0.0):
            self.__red.set_active(True)
        elif self.__cur_color == (0.0, 1.0, 0.0):
            self.__green.set_active(True)
        elif self.__cur_color == (0.0, 0.0, 1.0):
            self.__blue.set_active(True)
        else:
            self.__black.set_active(True)
            
        if self.__cur_pen == 2:
            self.__pencil.set_active(True)
        elif self.__cur_pen == 5:
            self.__brush.set_active(True)
            
    
    def submit_ink_cb(self, widget):
        if self.__arbiter.get_is_instructor():
            self.__logger.debug("Broadcast clicked")
            self.broadcast_ink()
        else:
            self.__logger.debug("Submit clicked")
            self.__submit.set_sensitive(False)
            self.__timer = threading.Timer(10.0, self.reenable_submissions)
            self.__timer.start()
            self.__arbiter.do_submit_ink()
        
    def broadcast_ink(self):
        self.__arbiter.do_broadcast_ink()
    
    def reenable_submissions(self):
        gtk.gdk.threads_enter()
        self.__submit.set_sensitive(True)
        self.__submit.queue_draw()
        gtk.gdk.threads_leave()
    
    def undo(self, widget):
        self.__arbiter.do_undo()
    
    def redo(self, widget):
        self.__arbiter.do_redo()
    
    def update_buttons(self, widget=None):
        can_undo, can_redo = self.__arbiter.get_can_undo_redo()
        self.__undo.set_sensitive(can_undo)
        self.__redo.set_sensitive(can_redo)
        if self.__arbiter.get_is_instructor():
            if self.__arbiter.get_active_submission() == -1:
                self.__submit.set_sensitive(False)
            else:
                self.__submit.set_sensitive(True)
