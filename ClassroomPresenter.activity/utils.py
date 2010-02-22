import os
import gtk

def getFileType(filename):
	return os.path.basename(filename).split('.').pop()

def copy_file(src, dest):
	f1 = open(src, "rb")
	data = f1.read()
	f1.close()
	f2 = open(dest, "wb")
	f2.write(data)
	f2.close()

def run_dialog(header,msg):
	"""Pops up a blocking dialog box with 'msg'"""
	dialog = gtk.Dialog(str(header), None, gtk.DIALOG_MODAL,
				(gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

	hbox = gtk.HBox(False, 12)
	hbox.set_border_width(12)
	dialog.vbox.pack_start(hbox, True, True, 0)
	hbox.show()
	
	label = gtk.Label(str(msg))
	hbox.pack_start(label, False, False, 0)
	label.show()

	dialog.run()
	dialog.destroy()
