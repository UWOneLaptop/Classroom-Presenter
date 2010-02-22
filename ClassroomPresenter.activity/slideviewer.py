# slideviewer.py
#
# Class for displaying Classroom Presenter SVG slides in a GTK widget
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

import cairo
import rsvg
import gtk
import os
import time
import ink
import logging
import gobject

TOOL_PEN = 0
TOOL_ERASER = 1

class SlideViewer(gtk.EventBox):
    __gsignals__ = {'button_press_event' : 'override',
                    'button_release_event' : 'override',
                    'motion_notify_event' : 'override',
                    'enter_notify_event'    : 'override',
                    'undo-redo-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
                    }
    
    erase_res = 8
    inkmap_size = 2048
    
    def __init__(self, arbiter):
        gtk.EventBox.__init__(self)

        self.__arbiter = arbiter

        self.__logger = logging.getLogger('SlideViewer')
        self.__logger.setLevel(logging.DEBUG)

        self.__canvas = SlideViewerCanvas(arbiter)
        self.add(self.__canvas)
        self.__canvas.show()
        self.__arbiter.connect_slide_redraw(self.show_current)
        self.__arbiter.connect_remote_ink_added(self.remote_ink_added)
        self.__arbiter.connect_remove_path(self.instr_remove_ink)
        self.__cur_path = None
        self.__tool = TOOL_PEN
        
        # default color-blue and pen-4
        self.set_pen(4)
        self.set_color(0.0, 0.0, 1.0)
    
    def set_color(self, r, g, b):
        self.__canvas.cur_color = (r, g, b)
        
    def get_color(self):
        return self.__canvas.get_color()
    
    def set_pen(self, size):
        self.__canvas.cur_pen = size
        self.__tool = TOOL_PEN
    
    def set_eraser(self):
        self.__tool = TOOL_ERASER
        
    def get_pen(self):
        return self.__canvas.get_pen()
    
    def show_current(self, widget):
        """Handle a slide-redraw event by showing the current slide."""
        self.show_slide()
    
    def show_slide(self, n=None):
        self.__canvas.show_slide(n)
        
    def remote_ink_added(self, event, inkstr):
        self.__canvas.add_ink_path(ink.Path(inkstr), ink_from_instr=True)
        self.__canvas.queue_draw()
    
    def clear_ink(self):
        if self.__arbiter.get_sharing_mode():
            self.__canvas.instr_ink = []
        if self.__arbiter.get_active_submission() == -1:
            self.__canvas.self_ink = []
        self.__canvas.queue_draw()
    
    def instr_remove_ink(self, widget, uid):
        for path in self.__canvas.instr_ink:
            if path.uid == uid:
                self.__canvas.instr_ink.remove(path)
        self.__canvas.queue_draw()
    
    def can_undo_redo(self):
        if self.__arbiter.get_active_submission() == -1 or self.__arbiter.get_sharing_mode():
            if self.__arbiter.get_sharing_mode():
                return ((len(self.__canvas.instr_ink) > 0), (len(self.__canvas.redo_stack) > 0))
            else:
                return ((len(self.__canvas.self_ink) > 0), (len(self.__canvas.redo_stack) > 0))
        else:
            return (False, False)
    
    def undo(self):
        if self.__arbiter.get_sharing_mode():
            undo_stack = self.__canvas.instr_ink
        else:
            undo_stack = self.__canvas.self_ink
        if len(undo_stack) > 0:
            path = undo_stack.pop()
            self.__arbiter.do_remove_local_path_by_uid(path.uid)
            self.__canvas.redo_stack.append(path)
            self.__canvas.queue_draw()
            self.emit('undo-redo-changed')
    
    def redo(self):
        if len(self.__canvas.redo_stack) > 0:
            path = self.__canvas.redo_stack.pop()
            self.__arbiter.do_add_ink_to_slide(str(path), local_request=True)
            if self.__arbiter.get_sharing_mode():
                self.__canvas.instr_ink.append(path)
            else:
                self.__canvas.self_ink.append(path)
            self.__canvas.queue_draw()
            self.emit('undo-redo-changed')
    
    def do_button_press_event(self, event):
        if self.__arbiter.get_active_submission() == -1 or self.__arbiter.get_sharing_mode():
            if self.__tool == TOOL_PEN:
                self.__last_pos = (event.x, event.y)
                self.__cur_path = ink.Path()
                self.__cur_path.color = self.__canvas.cur_color
                self.__cur_path.pen = self.__canvas.cur_pen    
                self.__cur_path.add((event.x, event.y));
                self.__canvas.add_ink_path(self.__cur_path)
            elif self.__tool == TOOL_ERASER:
                to_erase = self.__canvas.inkmap.query(event.x / SlideViewer.erase_res, 
                    event.y / SlideViewer.erase_res)
                for path in to_erase:
                    self.__arbiter.do_remove_local_path_by_uid(path.uid)
                    self.__canvas.queue_draw()
                    self.__logger.debug("erase path: "+str(path))
    
    def do_button_release_event(self, event):
        if self.__cur_path:
            self.__cur_path.add((event.x, event.y));
            self.__arbiter.do_add_ink_to_slide(str(self.__cur_path), local_request=True)
            self.__cur_path = None
            self.__canvas.redo_stack = []
            self.emit('undo-redo-changed')

            
    def do_motion_notify_event(self, event):
        if self.__tool == TOOL_PEN:
            if self.__cur_path:
                self.__pos = (event.x, event.y)
                if(self.has_moved()):
                    self.__canvas.draw_ink_seg_immed(self.__last_pos, self.__pos)
                    self.__canvas.inkmap.insert_seg(self.__last_pos[0] / SlideViewer.erase_res,
                        self.__last_pos[1] / SlideViewer.erase_res,
                        self.__pos[0] / SlideViewer.erase_res,
                        self.__pos[1] / SlideViewer.erase_res, 
                        self.__cur_path)
                    self.__cur_path.add((event.x, event.y));
                    self.__last_pos = self.__pos
        
    def has_moved(self):
        deltaX = self.__pos[0] - self.__last_pos[0]
        deltaY = self.__pos[1] - self.__last_pos[1]
        return (deltaX > 3 or deltaX < -3 or deltaY > 3 or deltaY < -3)
        
    def do_enter_notify_event(self, event):
        self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.PENCIL))

class SlideViewerCanvas(gtk.DrawingArea):
    __gsignals__ = {'expose_event' : 'override',
                    'configure_event' : 'override',
                    }
    
    

    def __init__ (self, arbiter):
        gtk.DrawingArea.__init__ (self)

        self.__arbiter = arbiter

        self.__logger = logging.getLogger('SlideViewerCanvas')
        self.__logger.setLevel('error')

        self.__surface = None
        self.instr_ink = []
        self.self_ink = []
        self.redo_stack = []
        self.cur_pen = None
        self.cur_color = None
        self.inkmap = ink.InkMap(SlideViewer.inkmap_size)
            
    def show_slide(self, n=None):
        timerstart = time.time()
        x, y, width, height = self.allocation
        self.__surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        self.__arbiter.do_render_slide_to_surface(self.__surface, n)
        self.instr_ink = []
        self.self_ink = []
        self.redo_stack = []
        instr = self.__arbiter.get_instructor_ink()
        selfink, text = self.__arbiter.get_self_ink_or_submission()
        for path in instr:
            self.instr_ink.append(ink.Path(path))
        for path in selfink:
            self.self_ink.append(ink.Path(path))
        self.queue_draw()
        self.__logger.debug("Rendering slide took " + str(time.time() - timerstart) + " seconds")
    
    def add_ink_path(self, path, ink_from_instr=False):
        if self.__arbiter.get_sharing_mode() or ink_from_instr:
            self.instr_ink.append(path)
        else:
            self.self_ink.append(path)
    
    def draw_ink_seg_immed(self, start, end):
        self.__context = self.window.cairo_create()
        self.__context.set_line_cap(cairo.LINE_CAP_ROUND)
        self.__context.set_line_join(cairo.LINE_JOIN_ROUND)
        self.__context.set_source_rgb(self.cur_color[0], self.cur_color[1], self.cur_color[2])
        self.__context.set_line_width(self.cur_pen)
        self.__context.move_to(start[0], start[1])
        self.__context.line_to(end[0], end[1])
        self.__context.stroke()
    
    def do_configure_event(self, event):
        """Reload the slide when assigned a new height/width"""
        #if self.__renderer:
        self.show_slide()

    def do_expose_event (self, event):
        """Draw the slide surface into the DrawingArea"""
        timerstart = time.time()
        if self.__surface:
            # Draw the (cached) slide
            self.__context = self.window.cairo_create()
            self.__context.set_source_surface(self.__surface, 0, 0)
            self.__context.paint()
            self.__context.set_line_cap(cairo.LINE_CAP_ROUND)
            self.__context.set_line_join(cairo.LINE_JOIN_ROUND)
            is_instr = self.__arbiter.get_sharing_mode()
            self.draw_ink_paths(self.instr_ink, is_instr)
            self.draw_ink_paths(self.self_ink, not is_instr)
            
        self.__logger.debug("Exposing slide took " + str(time.time() - timerstart) + " seconds")
            

    def draw_ink_paths(self, paths, mine):
        if mine:
            self.inkmap = ink.InkMap(SlideViewer.inkmap_size)
        for path in paths:
            self.__context.set_line_width(path.pen)
            self.__context.set_source_rgb(path.color[0], path.color[1], path.color[2])
            start = True
            for point in path.points:
                if start:
                    prev = (point[0], point[1])
                    self.__context.move_to(point[0], point[1])
                    start = False
                else:
                    self.__context.line_to(point[0], point[1])
                    if mine:
                        self.inkmap.insert_seg(prev[0] / SlideViewer.erase_res, 
                            prev[1] / SlideViewer.erase_res, 
                            point[0] / SlideViewer.erase_res, 
                            point[1] / SlideViewer.erase_res, 
                            path)
                        prev = (point[0], point[1])
            self.__context.stroke()
            
    def get_pen(self):
        return self.cur_pen
    
    def get_color(self):
        return self.cur_color
    

class ThumbViewer(gtk.DrawingArea):
    
    __gsignals__  = {'expose_event' : 'override',
                    }
    
    def __init__ (self, arbiter, n):
        gtk.DrawingArea.__init__ (self)

        self.__arbiter = arbiter

        self.__logger = logging.getLogger('ThumbViewer')
        self.__logger.setLevel('error')
        
        self.__n = n
        self.__was_highlighted = False
        self.__arbiter.connect_slide_redraw(self.slide_changed)
        
        # Load thumbnail from the PNG file, if it exists; otherwise draw from scratch
        timerstart = time.time()
        thumb = self.__arbiter.get_slide_thumb(n)
        if thumb and os.path.exists(thumb):
            self.__surface = cairo.ImageSurface.create_from_png(thumb)
        else:
            self.__surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 150)
            self.__arbiter.do_render_slide_to_surface(self.__surface, n)
            
            # Cache thumbnail
            name = "slide" + str(n) + "_thumb.png"
            thumb = os.path.join(self.__arbiter.get_deck_path(), name)
            self.__surface.write_to_png(thumb)
            self.__arbiter.do_set_slide_thumb(name, n)
        self.__logger.debug("Thumbnail loading/drawing took " + str(time.time() - timerstart) + " seconds")

    
    def do_expose_event (self, event):
        """Redraws the slide thumbnail view"""
        timerstart = time.time()
        ctx = self.window.cairo_create()
        x, y, width, height = self.allocation
        if self.__n == self.__arbiter.get_slide_index():
            ctx.set_source_rgb(0, 1.0, 0)
            self.__was_highlighted = True
        else:
            ctx.set_source_rgb(0.7, 0.7, 0.7)
            self.__was_highlighted = False
        ctx.rectangle(0, 0, width, height)
        ctx.fill()
        if self.__surface:
            ctx.set_source_surface(self.__surface, 0, 0)
            ctx.rectangle(5, 5, 200, 150)
            ctx.fill()
        self.__logger.debug("Exposing slide thumbnail took " + str(time.time() - timerstart) + " seconds")
     
    def slide_changed(self, widget):
        """Updates highlighting, if necessary, when current slide changes"""
        if self.__was_highlighted != (self.__n == self.__arbiter.get_slide_index()):
            self.queue_draw()
