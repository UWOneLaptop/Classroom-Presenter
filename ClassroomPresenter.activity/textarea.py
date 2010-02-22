# textarea.py
#
# Class to show, save, submit text entries
# 
# W.Burnside <wburnsid@u.washington.edu>
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


import pygtk
import gtk
import logging

class TextArea(gtk.HBox):

    def __init__(self, arbiter):
        gtk.HBox.__init__(self)
        
        self.__arbiter = arbiter

        self.__logger = logging.getLogger('TextArea')
        self.__logger.setLevel(logging.DEBUG)

        self.__text_area = gtk.Entry()
        self.render_text_area()
        self.__arbiter.connect_slide_redraw(self.update_text)
        self.__arbiter.connect_shared(self.shared_cb)
        self.__arbiter.connect_joined(self.shared_cb)
        self.__text_area.connect('changed', self.text_changed)
        self.__logger.debug("Hello from TextArea.")
        self.__is_shared = False
        self.update_text()

    def shared_cb(self, widget=None):
        self.__is_shared = True
        self.update_text()
    
    def update_text(self, widget=None):
        selfink, text = self.__arbiter.get_self_ink_or_submission()
        self.__text_area.set_text(text)
        if self.__arbiter.get_active_submission() == -1 and not self.__arbiter.get_is_instructor() and self.__is_shared:
            self.__text_area.set_sensitive(True)
            self.__logger.debug("sensitizing text area " + str(self.__arbiter.get_is_instructor()))
        else:
            self.__text_area.set_sensitive(False)
            self.__logger.debug("desensitizing text area")
    
    def text_changed(self, entry):
        if self.__arbiter.get_active_submission() == -1:
            self.__arbiter.do_set_slide_text(self.__text_area.get_text())
        
    def render_text_area(self, widget=None):
        
        # pack widgets
        self.pack_start(self.__text_area, True, True, 0)
        
        # show widgets
        self.__text_area.show()
        self.show()
    
    # Clear text in entry box
    def clear_text(self, widget, event):
        self.__text_area.set_text("")
    
    
