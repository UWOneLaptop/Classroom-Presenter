# slideshow.py
#
# Classes to represent a deck of slides, and handle things like file I/O and
# formats
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


import os
import xml.dom.minidom
import gobject
import logging

class Deck(gobject.GObject):
	
	__gsignals__ = {
		'slide-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
		'slide-redraw' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
		'remove-path' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT,)),
		'deck-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
		'local-ink-added' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
		'remote-ink-added' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
		'ink-submitted' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING, gobject.TYPE_STRING)),
		'ink-broadcast' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, 
							(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING)),
		'update-submissions' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT,)),
		'instructor-ink-cleared' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT,)),
		'instructor-ink-removed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT, gobject.TYPE_INT)),
	}
	
	def __init__(self, arbiter, base="/nfs/show"):
		gobject.GObject.__init__(self)
		
		self.__arbiter = arbiter
		self.__base = base

		self.__logger = logging.getLogger('Deck')
		self.__logger.setLevel(logging.DEBUG)

		self.__active_sub = -1
		self.__self_text = ""
		self.__text_tag = None
		
		# Compute the path to the deck.xml file and read it if it exists;
		# otherwise we'll create a new XML Document
		self.__xmlpath = os.path.join(base, "deck.xml")
		self.reload()
			
	def reload(self):
		self.__logger.debug("Reading deck")
		if os.path.exists(self.__xmlpath):
			self.__dom = xml.dom.minidom.parse(self.__xmlpath)
		else:
			self.__dom = xml.dom.minidom.Document()

		# Look for the root deck element; create it if it's not there
		decks = self.__dom.getElementsByTagName("deck")
		if len(decks) > 0:
			self.__deck = decks[0]
		else:
			self.__deck = self.__dom.createElement("deck")
			self.__dom.appendChild(self.__deck)
			splash = self.__dom.createElement("slide")
			layer = self.__dom.createElement("layer")
			layer.appendChild(self.__dom.createTextNode("splash.svg"))
			splash.appendChild(layer)
			self.__deck.appendChild(splash)

		# Get the slides from the show
		self.__slides = self.__deck.getElementsByTagName("slide")
		self.__nslides = len(self.__slides)
		self.__logger.debug(str(self.__nslides) + " slides in show")
		self.goto_slide(0, local_request=True)
		self.emit("deck-changed")
	
	def save(self, path=None):
		"""Writes the XML DOM in memory out to disk"""
		if not path:
			path = self.__xmlpath
		outfile = open(path, "w")
		self.__dom.writexml(outfile)
		outfile.close()
	
	def get_deck_path(self):
		"""Returns the path to the folder that stores this slide deck"""
		return self.__base
	
	def get_slide_layers(self, n=-1):
		"""Returns a list of the layers that comprise this slide"""
		if n == -1:
			n = self.__pos
		slide = self.__slides[n]
		self.__layers = slide.getElementsByTagName("layer")
		layers = []
		for l in self.__layers:
			p = os.path.join(self.__base, l.firstChild.nodeValue)
			layers.append(p)
		return layers
	
	def get_instructor_ink(self):
		self.__instructor_ink = []
		instr = self.__slide.getElementsByTagName("instructor")
		if len(instr) > 0:
			self.__instructor_tag = instr[0]
			pathtags = self.__instructor_tag.getElementsByTagName("path")
			for pathstr in pathtags:
				self.__instructor_ink.append(pathstr.firstChild.nodeValue)
		return self.__instructor_ink
		
	def get_self_ink_or_submission(self):
		if self.__active_sub == -1:
			return (self.__self_ink, self.__self_text)
		subtags = self.__slide.getElementsByTagName("submission")
		if self.__active_sub > -1 and self.__active_sub < len(subtags):
			active_subtag = subtags[self.__active_sub]
			text = ""
			texts = active_subtag.getElementsByTagName("text")
			if len(texts) > 0:
				if texts[0].firstChild:
					text = texts[0].firstChild.nodeValue
			pathlist = []
			paths = active_subtag.getElementsByTagName("path")
			for path in paths:
				if path.firstChild:
					pathlist.append(path.firstChild.nodeValue)
			return (pathlist, text)
		return None
	
	def set_active_submission(self, sub):
		self.__active_sub = sub
		self.emit('slide-redraw')
	
	def get_active_submission(self):
		return self.__active_sub
	
	def get_submission_list(self, n=None):
		if n is None:
			n = self.__pos
		subtags = self.__slide.getElementsByTagName("submission")
		sublist = []
		for subtag in subtags:
			sublist.append(subtag.getAttribute("from"))
		return sublist
	
	def add_submission(self, whofrom, inks, text="", n=None):
		if n is None:
			n = self.__pos
		if n >= 0 and n < self.get_slide_count():
			slide = self.__slides[n]
		else:
			slide = self.__slides[self.__pos]
		newsub = self.__dom.createElement("submission")
		newsub.setAttribute("from", whofrom)
		substrparts = inks.split("$")
		for part in substrparts:
			if len(part) > 0:
				newpath = self.__dom.createElement("path")
				newpath.appendChild(self.__dom.createTextNode(part))
				newsub.appendChild(newpath)
		subtext = self.__dom.createElement("text")
		subtext.appendChild(self.__dom.createTextNode(text))
		newsub.appendChild(subtext)
		subs = slide.getElementsByTagName("submission")
		for sub in subs:
			if sub.getAttribute("from") == whofrom:
				slide.removeChild(sub)
		slide.appendChild(newsub)
		subs = slide.getElementsByTagName("submission")
		if n == self.__pos:
			self.emit('update-submissions', len(subs) - 1)
	
	def add_ink_to_slide(self, pathstr, islocal, n=None):
		"""Adds ink to the current slide, or slide n if given.  Instructor ink may be added to any slide;
		but it only makes sense to add student ink to the current slide (n will be ignored)"""
		if n is None:
			slide = self.__slide
			instr_tag = self.__instructor_tag
			if instr_tag == None:
				instr_tag = self.__dom.createElement("instructor")
				slide.appendChild(instr_tag)
				self.__instructor_tag = instr_tag
		else:
			if n < self.get_slide_count() and n >= 0:
				slide = self.__slides[n]
			else:
				slide = self.__slides[self.__pos]
			instr_tags = slide.getElementsByTagName("instructor")
			if len(instr_tags) > 0:
				instr_tag = instr_tags[0]
			else:
				instr_tag = self.__dom.createElement("instructor")
				slide.appendChild(instr_tag)
		if not islocal or self.__arbiter.get_sharing_mode():
			self.__instructor_ink.append(pathstr)
			path = self.__dom.createElement("path")
			path.appendChild(self.__dom.createTextNode(pathstr))
			instr_tag.appendChild(path)
		else:
			self.__self_ink.append(pathstr)
			if not self.__self_ink_tag:
				self.__self_ink_tag = self.__dom.createElement("self")
				self.__slide.appendChild(self.__self_ink_tag)
			path = self.__dom.createElement("path")
			path.appendChild(self.__dom.createTextNode(pathstr))
			self.__self_ink_tag.appendChild(path)
		if islocal:
			self.emit("local-ink-added", pathstr)
		else:
			if n is None or n == self.__pos:
				self.emit("remote-ink-added", pathstr)
	
	def clear_ink(self, n=None):
		if n is None:
			n = self.__pos
		slide = self.__slides[n]
		if self.__arbiter.get_sharing_mode():
			self.clear_instructor_ink(n)
			self.emit('instructor-ink-cleared', n)
		self_tags = slide.getElementsByTagName("self")
		for self_tag in self_tags:
			slide.removeChild(self_tag)
		self.__self_ink = []
		self.__self_ink_tag = None
	
	def clear_instructor_ink(self, n=None):
		if n is None:
			n = self.__pos
		slide = self.__slides[n]
		instructor_tags = slide.getElementsByTagName("instructor")
		for instructor_tag in instructor_tags:
			slide.removeChild(instructor_tag)
		if n == self.__pos:
			self.__instructor_ink = []
			self.__instructor_tag = None
			self.emit('slide-redraw')
	
	def remove_instructor_path_by_uid(self, uid, n=None):
		if n is None:
			n = self.__pos
		needs_redraw = False
		slide = self.__slides[n]
		instructor_tags = slide.getElementsByTagName("instructor")
		if len(instructor_tags) > 0:
			instructor_tag = instructor_tags[0]
		else:
			return
		path_tags = instructor_tag.getElementsByTagName("path")
		for path_tag in path_tags:
			if path_tag.firstChild:
				pathstr = path_tag.firstChild.nodeValue
				path_uid = 0
				try:
					path_uid = int(pathstr[0:pathstr.find(';')]) 
				except Exception, e:
					pass
				if path_uid == uid:
					instructor_tag.removeChild(path_tag)
					needs_redraw = True
		if n == self.__pos and needs_redraw:
			self.emit('remove-path', uid)
	
	def remove_local_path_by_uid(self, uid, n=None):
		if n is None:
			n = self.__pos
		slide = self.__slides[n]
		if self.__arbiter.get_sharing_mode():
			self.emit('instructor_ink_removed', uid, n)
			tags = slide.getElementsByTagName("instructor")
		else:
			tags = slide.getElementsByTagName("self")
		if len(tags) > 0:
			tag = tags[0]
		else:
			return
		path_tags = tag.getElementsByTagName("path")
		for path_tag in path_tags:
			if path_tag.firstChild:
				pathstr = path_tag.firstChild.nodeValue
				path_uid = 0
				try:
					path_uid = int(pathstr[0:pathstr.find(';')]) 
				except Exception, e:
					pass
				if path_uid == uid:
					tag.removeChild(path_tag)
						
	def submit_ink(self):
		inks, text, whofrom = self.getSerializedInkSubmission()
		self.__logger.debug("Submitting ink: " + str(inks) + " text: " + text)
		self.emit('ink-submitted', inks, text)
		
	def broadcast_ink(self):
		inks, text, whofrom = self.getSerializedInkSubmission()
		self.emit('ink-broadcast', whofrom, inks, text)
	
	def getSerializedInkSubmission(self):
		sub = ""
		text = ""
		if self.__active_sub == -1:
			self_tags = self.__slide.getElementsByTagName("self")
			if len(self_tags) > 0:
				texts = self_tags[0].getElementsByTagName("text")
				if len(texts) > 0:
					if texts[0].firstChild:
						text = texts[0].firstChild.nodeValue
				for path in self_tags[0].getElementsByTagName("path"):
					sub = sub + path.firstChild.nodeValue + "$"
			return sub, text, "myself"
		else:
			sub = ""
			whofrom = "unknown"
			subtags = self.__slide.getElementsByTagName("submission")
			if self.__active_sub > -1 and self.__active_sub < len(subtags):
				active_subtag = subtags[self.__active_sub]
				text = ""
				whofrom = active_subtag.getAttribute("from")
				texts = active_subtag.getElementsByTagName("text")
				if len(texts) > 0:
					if texts[0].firstChild:
						text = texts[0].firstChild.nodeValue
				pathlist = []
				paths = active_subtag.getElementsByTagName("path")
				for path in paths:
					if path.firstChild:
						sub = sub + path.firstChild.nodeValue + "$"
			return sub, text, whofrom
	
	def get_slide_thumb(self, n=-1):
		"""Returns the full path to the thumbnail for this slide if it is defined; otherwise False"""
		if n == -1:
			n = self.__pos
		slide = self.__slides[n]
		thumbs = slide.getElementsByTagName("thumb")
		if len(thumbs) < 1:
			return False
		return os.path.join(self.__base, thumbs[0].firstChild.nodeValue)
	
	def set_slide_thumb(self, filename, n=-1):
		"""Sets the thumbnail for this slide to filename (provide a *relative* path!)"""
		if n == -1:
			n = self.__pos
		slide = self.__slides[n]
		thumbs = slide.getElementsByTagName("thumb")
		for t in thumbs:
			slide.removeChild(t)
		thumb = self.__dom.createElement("thumb")
		thumb.appendChild(self.__dom.createTextNode(filename))
		slide.appendChild(thumb)
	
	def set_slide_text(self, textval):
		self.__self_text = textval
		if self.__text_tag:
		 	if self.__text_tag.firstChild:
				self.__text_tag.firstChild.nodeValue = textval
			else:
				self.__text_tag.appendChild(self.__dom.createTextNode(textval))
			
		
	def doNewIndex(self):
		"""Updates any necessary state associated with moving to a new slide"""
		self.__slide = self.__slides[self.__pos]
		self_ink = self.__slide.getElementsByTagName("self")
		self.__instructor_tag = None
		self.__self_ink_tag = None
		self.__instructor_ink = []
		self.__self_ink = []
		self.__self_text = ""
		self.__text_tag = None
		self.__active_sub = -1
		if len(self_ink) > 0:
			self.__self_ink_tag = self_ink[0]
			texttags = self.__self_ink_tag.getElementsByTagName("text")
			if len(texttags) > 0:
				self.__text_tag = texttags[0]
			else:
				self.__text_tag = self.__dom.createElement("text")
				self.__text_tag.appendChild(self.__dom.createTextNode(""))
				self.__self_ink_tag.appendChild(self.__text_tag)
			pathtags = self.__self_ink_tag.getElementsByTagName("path")
			for pathstr in pathtags:
				self.__self_ink.append(pathstr.firstChild.nodeValue)
		else:
			self.__self_ink_tag = self.__dom.createElement("self")
			self.__slide.appendChild(self.__self_ink_tag)
			self.__text_tag = self.__dom.createElement("text")
			self.__text_tag.appendChild(self.__dom.createTextNode(""))
			self.__self_ink_tag.appendChild(self.__text_tag)
		if self.__text_tag.firstChild:
			self.__self_text = self.__text_tag.firstChild.nodeValue
			
		self.emit("slide-changed")
		self.emit("update-submissions", self.__active_sub)
		self.emit("slide-redraw")
		
	def goto_slide(self, index, local_request):
		"""Jumps to the slide at the given index, if it's valid"""
		nav_locked = self.__arbiter.get_lock_mode()
		shared = self.__arbiter.get_sharing_mode()
		in_range = index < self.__nslides and index >= 0

		self.__logger.debug("Trying to change slides: locked? %u, instructor? %u, local_request? %u",
							nav_locked, shared, local_request)

		if (shared or not local_request or not nav_locked) and in_range:
			self.__logger.debug("Changing slide to index: %u", index)
			self.__pos = index
			self.doNewIndex()
	
	def get_slide_index(self):
		"""Returns the index of the current slide"""
		return self.__pos
	
	def next_slide(self):
		"""Moves to the next slide"""
		self.goto_slide(self.__pos + 1, local_request=True)
	
	def previous_slide(self):
		"""Moves to the previous slide"""
		self.goto_slide(self.__pos - 1, local_request=True)
		
	def is_at_beginning(self):
		"""Returns true if show is on the first slide in the deck"""
		if self.__nslides < 1:
			return True
			
		if self.__pos == 0:
			return True
		else:
			return False
	
	def is_at_end(self):
		"""Returns true if the show is at the last slide in the deck"""
		if self.__nslides < 1:
			return True
			
		if self.__pos == self.__nslides - 1:
			return True
		else:
			return False
	
	def get_slide_dimensions_from_xml(self, n=-1):
		"""Returns the dimensions for the slide at index n, if they're specified"""
		if n == -1:
			n = self.__pos
		slide = self.__slides[n]
		wstring = slide.getAttribute("width")
		hstring = slide.getAttribute("height")
		if wstring != '' and hstring != '':
			return [float(wstring), float(hstring)]
		return False
			
	def get_slide_count(self):
		return self.__nslides
			
gobject.type_register(Deck)
