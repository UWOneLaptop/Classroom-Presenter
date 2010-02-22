# classroompresenter.py
#
# Classroom Presenter for the XO Laptop
# Main class
# B. Mayton <bmayton@cs.washington.edu>
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

from sugar.activity import activity
import logging

import sys, os
import gtk
import zipfile
import gobject

import slideviewer
import sidebar
import sliderenderer
import slideshow
import textarea
import toolbars
import arbiter
import utils
import shared
import time
import pdb

from gettext import gettext as _

gtk.gdk.threads_init()

class ClassroomPresenter(activity.Activity):
        
    __gsignals__ = {
            'quitting' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
            }

    def __init__(self, handle):
        #pdb.set_trace()
        activity.Activity.__init__(self, handle)

        logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s')
        self.__logger = logging.getLogger('ClassroomPresenter')
        self.__logger.setLevel(logging.DEBUG)

        # Find our instance path
        self.__work_path = os.path.join(self.get_activity_root(), 'instance')
        self.__deck_dir = os.path.join(self.__work_path, 'deck')
        try:
            os.mkdir(self.__deck_dir)
        except Exception, e:
            self.__logger.debug("Caught exception and continuing: %s", e)
        self.__rsrc_dir = os.path.join(activity.get_bundle_path(), 'resources')
        self.__logger.debug("Found deck directory: %s", self.__deck_dir)        

        # Copy the splash screen to the working directory
        utils.copy_file(os.path.join(self.__rsrc_dir, 'splash.svg'),
                os.path.join(self.__deck_dir, 'splash.svg'))
        
        # the arbiter object handles all communication between classes
        self.__arbiter = arbiter.Arbiter(self)

        # deck object handles the slide show
        self.__deck = slideshow.Deck(self.__arbiter, self.__deck_dir)
        self.__arbiter.register_deck(self.__deck)

        # shared object takes care of all networking, activity sharing
        self.__shared = shared.Shared(self.__arbiter, self.__work_path)
        self.__arbiter.register_shared(self.__shared)

        # renders slides and thumbnails
        self.__renderer = sliderenderer.Renderer(self.__arbiter)
        self.__arbiter.register_renderer(self.__renderer)
        
        # Set up the main canvas
        self.__slide_view = gtk.HBox()
        self.set_canvas(self.__slide_view)
        
        # Set up Main Viewer box
        self.__main_view_box = gtk.VBox()
        self.__slide = slideviewer.SlideViewer(self.__arbiter) # main slide view
        self.__arbiter.register_slide_viewer(self.__slide)
        self.__text_area = textarea.TextArea(self.__arbiter) # text input widget
        self.__arbiter.register_text_area(self.__text_area)
        self.__main_view_box.pack_start(self.__slide, True, True, 5)
        self.__main_view_box.pack_start(self.__text_area, False, False, 0)
        
        # Create our toolbars
        navTB = toolbars.NavToolBar(self.__arbiter)
        self.__arbiter.register_nav_tb(navTB)
        inkTB = toolbars.InkToolBar(self.__arbiter)
        self.__arbiter.register_ink_tb(inkTB)
        
        # Create the standard activity toolbox; add our toolbars
        toolbox = activity.ActivityToolbox(self)
        toolbox.add_toolbar(_("Navigation"),navTB)
        toolbox.add_toolbar(_("Ink"), inkTB)
        self.set_toolbox(toolbox)
        toolbox.show()
        
        # Set up the side scrollbar widget
        self.__side_bar = sidebar.SideBar(self.__arbiter)
        self.__side_bar.set_size_request(225, 100)
        
        # Set up a separator for the two widgets
        separator = gtk.VSeparator()
        
        # Pack widgets into main window
        self.__slide_view.pack_start(self.__main_view_box, True, True, 0)
        self.__slide_view.pack_start(separator, False, False, 5)
        self.__slide_view.pack_start(self.__side_bar, False, False, 0)
        
        # Show all widgets
        self.__slide_view.show_all()
        self.__main_view_box.show()
        self.__slide.show()
        self.__text_area.show()
        separator.show()
        self.__side_bar.show_all()
        
        # Set up the progress view
        self.__progress_max = 1.0
        self.__progress_cur = 0.01
        self.__progress_view = gtk.VBox()
        self.__progress_lbl = gtk.Label(_("Loading slide deck..."))
        self.__progress_bar = gtk.ProgressBar()
        self.__progress_view.pack_start(self.__progress_lbl, True, False, 5)
        #self.__progress_view.pack_start(self.__progress_bar, False, False, 5)
        self.__progress_bar.set_fraction(self.__progress_cur / self.__progress_max)
        
        self.__arbiter.connect_deck_download_complete(self.dl_complete_cb)
    
    def dl_complete_cb(self, widget):
        self.do_slideview_mode()
    
    def do_slideview_mode(self):
        self.set_canvas(self.__slide_view)
        self.__slide_view.show_all()
    
    def set_progress_max(self, maxval):
        self.__progress_max = maxval
        self.__progress_bar.set_fraction(float(self.__progress_cur) / float(self.__progress_max))
    
    def do_progress_view(self):
        self.set_canvas(self.__progress_view)
        self.__progress_view.show_all()
        
    def set_progress(self, val):
        self.__progress_cur = val
        self.__progress_bar.set_fraction(float(self.__progress_cur) / float(self.__progress_max))

    def can_close(self):
        """ Overrides the inherited method. Tells us the activity wants to quit. """
        self.emit('quitting'); # lets everyone know we're quitting, to do any last minute work
        return True
            
    def read_file(self, file_path):
        self.__logger.debug("read_file " + str(file_path))
        ftype = utils.getFileType(file_path)
        z = zipfile.ZipFile(file_path, "r")
        for i in z.infolist():
            f = open(os.path.join(self.__deck_dir, i.filename), "wb")
            f.write(z.read(i.filename))
            f.close()
        z.close()
        self.__arbiter.do_reload_deck()
        newindex = 0
        if 'current_index' in self.metadata:
            newindex = int(self.metadata.get('current_index', '0'))
        self.__arbiter.do_goto_slide(newindex, local_request=False)
    
    def write_file(self, file_path):
        self.__logger.debug("write_file " + str(file_path))
        self.metadata['mime_type'] = "application/x-classroompresenter"
        self.metadata['current_index'] = str(self.__arbiter.get_slide_index())
        self.__arbiter.do_deck_save()
        z = zipfile.ZipFile(file_path, "w")
        root, dirs, files = os.walk(self.__deck_dir).next()
        for f in files:
            z.write(os.path.join(root, f), f)
        z.close()
        
    def get_shared_activity(self):
        return self._shared_activity        
