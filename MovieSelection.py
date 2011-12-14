#!/usr/bin/python
# encoding: utf-8
#
# Copyright (C) 2011 by Coolman & Swiss-MAD
#
# In case of reuse of this source code please do not remove this copyright.
#
#	This program is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	For more information on the GNU General Public License see:
#	<http://www.gnu.org/licenses/>.
#

from Components.ActionMap import ActionMap, HelpableActionMap
from Components.Button import Button
from Components.config import *
from Components.Label import Label
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Screens.LocationBox import LocationBox
from Tools import Notifications
from Tools.BoundFunction import boundFunction
from enigma import getDesktop, eServiceReference, eTimer

import os
from time import time

# Movie preview
from Components.VideoWindow import VideoWindow

# Cover
from Components.AVSwitch import AVSwitch
from Components.Pixmap import Pixmap
from enigma import ePicLoad
#from Tools.LoadPixmap import LoadPixmap

# EMC internal
from DelayedFunction import DelayedFunction
from EnhancedMovieCenter import _
from EMCTasker import emcTasker, emcDebugOut
from MovieCenter import MovieCenter
from MovieSelectionMenu import MovieMenu
from EMCMediaCenter import EMCMediaCenter
from VlcPluginInterface import VlcPluginInterfaceSel
from CutListSupport import CutList
from DirectoryStack import DirectoryStack
from E2Bookmarks import E2Bookmarks
from EMCBookmarks import EMCBookmarks
from ServiceSupport import ServiceEvent

from MovieCenter import extList, extVideo, extMedia, extDir, plyDVD, cmtBME2, cmtBMEMC
global extList, extVideo, extMedia, extDir, plyDVD, cmtBME2, cmtBMEMC

gMS = None


class SelectionEventInfo:
	def __init__(self):
		#from Components.Sources.ServiceEvent import ServiceEvent
		self["Service"] = ServiceEvent()
		# Movie preview
		self["Video"] = VideoWindow(decoder = 0)
		# Movie Cover
		self["Cover"] = Pixmap()
		#noCoverFile = resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/no_coverArt.png")
		#self.noCoverPixmap = LoadPixmap(noCoverFile)
		#self.noCoverPixmap = None

	def initPig(self):
		if config.EMC.movie_pig.value == "":
			print "EMC: InitPig"
			self["Cover"].hide()
			self["Video"].show()
			self.session.nav.playService(self.lastservice)
			self.lastservice = None
		elif config.EMC.movie_pig.value == "C":
			print "EMC: InitPig C"
			self["Video"].hide()
			self["Cover"].instance.setPixmap(None)
			#self["Cover"].show()
			self["Cover"].hide()
		elif config.EMC.movie_pig.value == "P":
			print "EMC: InitPig P"
			self["Cover"].hide()
			#self["Video"].show()
			self["Video"].hide()

	def updateEventInfo(self, service):
		self["Service"].newService(service)

	def showCover(self, service=None):
		if service:
			path = service.getPath()
			name, ext = os.path.splitext(path)
			ext = ext.lower()
			jpgpath = ""
			if ext in extMedia:
				jpgpath = name + ".jpg"
			elif os.path.isdir(path):
				jpgpath = os.path.join(path, "folder.jpg")
				#TODO avoid os.path.exists double check
				if jpgpath and not os.path.exists(jpgpath):
					jpgpath = os.path.join(path, os.path.basename(path)) + ".jpg"
			if jpgpath and os.path.exists(jpgpath):
				sc = AVSwitch().getFramebufferScale() # Maybe save during init
				self.picload = ePicLoad()
				self.picload.PictureData.get().append(self.showCoverCallback)
				size = self["Cover"].instance.size()
				self.picload.setPara((size.width(), size.height(), sc[0], sc[1], False, 1, "#00000000")) # Background dynamically
				self.picload.startDecode(jpgpath)
				#self["Cover"].show()
			else:
				#TODO test if reset has to be done really
				#self["Cover"].instance.setPixmap(None)#(self.noCoverPixmap)
				self["Cover"].hide()
		else:
			#TODO test if reset has to be done really
			#self["Cover"].instance.setPixmap(None)#(self.noCoverPixmap)
			self["Cover"].hide()

	def showCoverCallback(self, picInfo=None):
		if picInfo:
			ptr = self.picload.getData()
			if ptr != None:
				self["Cover"].instance.setPixmap(ptr)
				self["Cover"].show()

	# Movie preview
	def previewMovie(self, service=None):
		print "EMC: previewMovie"
		if service:
			# TODO can we reuse the EMCMediaCenter for the video preview
			# Start preview
			self.session.nav.playService(service)
			# Get service
			s = self.session.nav.getCurrentService()
			if s:
				ext = os.path.splitext(service.getPath())[1].lower()
				if ext in plyDVD:
					subs = getattr(s, "subtitle", None)
					if callable(subs):
						#self.dvdScreen = self.session.instantiateDialog(DVDOverlay)
						#subs.enableSubtitles(self.dvdScreen.instance, None)
						subs.enableSubtitles(None, None)
					from Screens.InfoBar import InfoBar
					infobar = InfoBar and InfoBar.instance
					if infobar:
						infobar.pauseService()
						infobar.unPauseService()
				else:
					# Get seek
					seekable = s.seek()
					if seekable:
						# Get cuesheet
						cue = s.cueSheet()
						if cue:
							# Avoid cutlist overwrite
							cue.setCutListEnable(False)
							# Adapted from jumpToFirstMark
							jumpto = None
							# EMC enhancement: increase recording margin to make sure we get the correct mark
							margin = config.recording.margin_before.value*60*90000 *2 or 20*60*90000
							middle = (long(seekable.getLength()[1]) or 90*60*90000) / 2
							# Search first mark
							for (pts, what) in cue.getCutList():
								if what == 3: #CUT_TYPE_LAST:
									jumpto = pts
									break
								if what == 2: #CUT_TYPE_MARK:
									if pts != None and ( pts < margin and pts < middle ):
										if jumpto == None or pts < jumpto: 
											jumpto = pts
											break
							if jumpto is not None:
								# Jump to first mark
								seekable.seekTo(jumpto)
				print "EMC: previewMovie show"
				self["Video"].show()
		else:
			self.session.nav.stopService() 
			self["Video"].hide()

class EMCSelection(Screen, HelpableScreen, SelectionEventInfo, VlcPluginInterfaceSel, DirectoryStack, E2Bookmarks, EMCBookmarks):
	def __init__(self, session):
		Screen.__init__(self, session)
		SelectionEventInfo.__init__(self)
		VlcPluginInterfaceSel.__init__(self)
		DirectoryStack.__init__(self)
		
		self.skinName = "EMCSelection"
		skin = None
		CoolWide = getDesktop(0).size().width()
		if CoolWide == 720:
			skin = "/usr/lib/enigma2/python/Plugins/Extensions/EnhancedMovieCenter/CoolSkin/EMCSelection_720.xml"
		elif CoolWide == 1024:
			skin = "/usr/lib/enigma2/python/Plugins/Extensions/EnhancedMovieCenter/CoolSkin/EMCSelection_1024.xml"
		elif CoolWide == 1280:
			skin = "/usr/lib/enigma2/python/Plugins/Extensions/EnhancedMovieCenter/CoolSkin/EMCSelection_1280.xml"
		if skin:
			Cool = open(skin)
			self.skin = Cool.read()
			Cool.close()
		
		self.playerInstance = None
		self.lastPlayedMovies = None
		self.multiSelectIdx = None
		self.returnService = None
		self.lastservice = None
		self.cursorDir = 0
		self["wait"] = Label(_("Reading directory..."))
		self["wait"].hide()
		self["list"] = MovieCenter()
		self["key_red"] = Button()
		self["key_green"] = Button()
		self["key_yellow"] = Button()
		self["key_blue"] = Button()
		global gMS
		gMS = self
		self["actions"] = HelpableActionMap(self, "PluginMovieSelectionActions",
			{
				"EMCOK":			(self.entrySelected,		_("Play selected movie(s)")),
#				"EMCOKL":			(self.unUsed,				"-"),
				"EMCPLAY":		(self.playAll,		_("Play All")),
				"EMCSHUFFLE":	(self.shuffleAll,		_("Shuffle All")),
				"EMCEXIT":		(self.abort, 				_("Close EMC")),
				"EMCMENU":		(self.openMenu,				_("Open menu")),
				"EMCINFO":		(self.showEventInformation,	_("Show event info")),
				"EMCINFOL":		(self.IMDbSearch,			_("IMDBSearch")),
				"EMCRed":			(self.deleteFile,			_("Delete file or empty dir")),
				"EMCSortMode":		(self.toggleSortMode,			_("Toggle sort mode")),
				"EMCSortOrder":		(self.toggleSortOrder,			_("Toggle sort order")),
				"EMCMOVE":		(self.moveMovie,			_("Move selected movie(s)")),
				"EMCCOPY":		(self.copyMovie,			_("Copy selected movie(s)")),
				"EMCBlue":		(self.blueFunc,				_("Movie home / Play last (configurable)")),
#				"EMCRedL":		(self.unUsed,				"-"),
#				"EMCGreenL":	(self.unUsed,				"-"),
				"EMCBlueL":		(self.openE2Bookmarks,		_("Open E2 bookmarks")),
#				"EMCBlueL":		(self.openEMCBookmarks,		_("Open EMC bookmarks")),
				"EMCLeft":		(self.pageUp,				_("Move cursor page up")),
				"EMCRight":		(self.pageDown,				_("Move cursor page down")),
				"EMCUp":			(self.moveUp,			_("Move cursor up")),
				"EMCDown":		(self.moveDown,			_("Move cursor down")),
				"EMCBqtPlus":	(self.moveTop,			_("Move cursor to the top")),
				"EMCBqtMnus":	(self.moveEnd,			_("Move cursor to the end")),
				"EMCArrowNext":	(self.CoolForward,		_("Directory forward")),
#				"EMCArrowNextL":	(self.unUsed,				"-"),
				"EMCArrowPrevious":	(self.CoolBack,			_("Directory back")),
#				"EMCArrowPreviousL":	(self.directoryUp,				_("Directory up")),
				"EMCVIDEOB":	(self.toggleSelectionList,		_("Toggle service selection")),
				"EMCVIDEOL":	(self.resetSelectionList,		_("Remove service selection")),
				"EMCAUDIO":		(self.openMenuPlugins,		_("Available plugins menu")),
#				"EMCAUDIOL":	(self.unUsed,				"-"),
				"EMCMENUL":		(self.openMenuPlugins,		_("Available plugins menu")),
				"EMCTV":			(self.triggerReloadList,			_("Reload movie file list")),
				"EMCTVL":			(self.CoolTimerList,			_("Open Timer List")),
				"EMCRADIO":		(self.toggleProgress,			_("Toggle viewed / not viewed")),
#				"EMCRADIOL":	(self.unUsed,				"-"),
				"EMCTEXT":		(self.multiSelect,			_("Start / end multiselection")),
#				"EMCTEXTL":		(self.unUsed,				"-"),
				"0":		(self.CoolKey0,					"-"),
				"4":		(self.CoolAVSwitch,			"-"),
				"7":		(self.CoolTVGuide,			"-"),
				"8":		(self.CoolSingleGuide,		"-"),
				"9":		(self.CoolEasyGuide,	"-"),
			}, prio=-1)
			# give them a little more priority to win over baseclass buttons
		self["actions"].csel = self
		
		HelpableScreen.__init__(self)
		
		self.currentPath = config.EMC.movie_homepath.value
		self.tmpSelList = None		# Used for file operations
		
		# Key press short long handling
		#TODO We have to rework this key press handling in order to allow different user defined color key functions
		self.toggle = True		# Used for long / short key press detection: Toggle sort mode / order, Toggle selection / reset selection 
		self.move = True
		self.busy = False			# Allow playback only in one mode: PlayEntry / PlayLast / PlayAll / ShuffleAll
		
		self.delayTimer = eTimer()
		self.delayTimer.callback.append(self.updateInfoDelayed)
		
		self.pigTimer = eTimer()
		self.pigTimer.callback.append(self.showPigDelayed)
		
		self.onShow.append(self.onDialogShow)
		self.onHide.append(self.onDialogHide)
		self["list"].onSelectionChanged.append(self.selectionChanged)

	def CoolAVSwitch(self):
		if config.av.policy_43.value == "pillarbox":
			config.av.policy_43.value = "panscan"
		elif config.av.policy_43.value == "panscan":
			config.av.policy_43.value = "scale"
		else:
			config.av.policy_43.value = "pillarbox"

	def CoolTVGuide(self):
		try:
			from Plugins.Extensions.CoolTVGuide.plugin import main
			main(self.session)
		except: return

	def CoolSingleGuide(self):
		try:
			from Plugins.Extensions.CoolTVGuide.CoolSingleGuide import CSGmain
			CSGmain(self.session)
		except: return

	def CoolEasyGuide(self):
		try:
			from Plugins.Extensions.CoolTVGuide.CoolEasyGuide import CEGmain
			CEGmain(self.session)
		except: return

	def CoolTimerList(self):
		from Screens.TimerEdit import TimerEditList
		self.session.open(TimerEditList)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		from EnhancedMovieCenter import EMCAbout
		self.session.open(MessageBox, EMCAbout, MessageBox.TYPE_INFO)

	def abort(self):
		if config.EMC.CoolStartHome.value:
			# Reload only if path is not movie home
			if self.currentPath != config.EMC.movie_homepath.value:
				DelayedFunction(1000, self.changeDir, config.EMC.movie_homepath.value)
		if self.playerInstance is not None:
			self.playerInstance.movieSelected(None)
		else:
			config.av.policy_43.cancel() # reload the default setting
			
			# Movie preview
			# Restore last service only if no player is active
			if self.lastservice:
				self.session.nav.playService(self.lastservice)
				self.lastservice = None
		self.close(None)

	def blueFunc(self):
		if config.EMC.movie_bluefunc.value == "MH":
			self.returnService = None
			self["list"].resetSorting()
			self.changeDir(config.EMC.movie_homepath.value)
		elif config.EMC.movie_bluefunc.value == "PL":
			self.playLast()

	def changeDir(self, path, service=None):
		path = os.path.normpath(path)
		self.returnService = service
		#TODOret if self.returnService: print "EMC ret chnSer " +str(self.returnService.toString())
		self.reloadList(path)

	def CoolKey0(self):
		# Movie home
		self.setStackNextDirectory( self.currentPath, self["list"].getCurrent() )
		self.changeDir(config.EMC.movie_homepath.value)

	def CoolForward(self):
		path, service = self.goForward( self.currentPath, self["list"].getCurrent() )
		if path and service:
			# Actually we are in a history folder - go forward
			self.changeDir(path, service)
		else:
			# No entry on stack
			# Move cursor to top of the list
			self.moveTop()

	def CoolBack(self):
		path, service = self.goBackward( self.currentPath, self["list"].getCurrent() )
		if path and service:
			# History folder is available - go back 
			self.changeDir(path, service)
		else:
			self.directoryUp()

	def directoryUp(self):
		path = None
		service = None
		if self.currentPath != "" and self.currentPath != "/":
			# Open parent folder
			self.setNextPath()
		else:
			# No entry on stack
			# Move cursor to top of the list
			self.moveTop()

	def setNextPath(self, nextdir = None, service = None):
		if nextdir == ".." or nextdir is None or nextdir.endswith(".."):
			if self.currentPath != "" and self.currentPath != "/":
				# Open Parent folder
				service = self["list"].getPlayerService(self.currentPath)
				nextdir = os.path.dirname(self.currentPath)
			else:
				# No way to go folder up
				return
		else:
			# Open folder nextdir and select given or first entry
			pass
		
		self.setStackNextDirectory( self.currentPath, self["list"].getCurrent() )
		self.changeDir(nextdir, service)

	def getCurrent(self):
		return self["list"].getCurrent()

	def moveUp(self):
		self.cursorDir = -1
		self["list"].instance.moveSelection( self["list"].instance.moveUp )

	def moveDown(self):
		self.cursorDir = 1
		self["list"].instance.moveSelection( self["list"].instance.moveDown )

	def pageUp(self):
		self.cursorDir = 0
		self["list"].instance.moveSelection( self["list"].instance.pageUp )

	def pageDown(self):
		self.cursorDir = 0
		self["list"].instance.moveSelection( self["list"].instance.pageDown )

	def moveTop(self):
		self["list"].instance.moveSelection( self["list"].instance.moveTop )

	def moveEnd(self):
		self["list"].instance.moveSelection( self["list"].instance.moveEnd )

	def multiSelect(self, index=-1):
		if self.browsingVLC(): return
		
		if index == -1:
			# User pressed the multiselect key
			if self.multiSelectIdx is None:
				# User starts multiselect
				index = self.getCurrentIndex()
				# Start new list with first selected item index
				self.multiSelectIdx = [index]
				# Toggle the first selected item
				self["list"].toggleSelection( index=index )
			else:
				# User stops multiselect
				# All items are already toggled
				self.multiSelectIdx = None
			self.updateTitle()
		else:	
			if self.multiSelectIdx:
				# Multiselect active
				firstIndex = self.multiSelectIdx[0]
				lastIndex = self.multiSelectIdx[-1]
				# Calculate step : selection and range step +1/-1 -> indicates the direction
				selStep = 1 - 2 * ( firstIndex > lastIndex)  # >=
				rngStep = 1 - 2 * ( lastIndex > index )
				if selStep == rngStep or firstIndex == lastIndex:
					start = lastIndex + rngStep
					end = index + rngStep
				elif index not in self.multiSelectIdx:
					start = lastIndex
					end = index + rngStep
				else:
					start = lastIndex
					end = index
				# Range from last selected to cursor position (both are included)
				for i in xrange(start, end, rngStep):
					if self.multiSelectIdx[0] == i:
						# Never untoggle the first index
						continue  # pass
					elif i not in self.multiSelectIdx:
						# Append index
						self.multiSelectIdx.append(i)
						# Toggle
						self["list"].toggleSelection( index=i )
					else:
						# Untoggle
						self["list"].toggleSelection( index=i )
						# Remove index
						self.multiSelectIdx.remove(i)
			else:
				emcDebugOut("[EMCMS] multiSelect Not active")

	def openE2Bookmarks(self):
		self.session.openWithCallback(
			self.openBookmarksCB,
			LocationBox,
				windowTitle = _("E2 Bookmark"),
				text = _("Open E2 Bookmark path"),
				currDir = str(self.currentPath)+"/",
				bookmarks = config.movielist.videodirs,
				autoAdd = False,
				editDir = True,
				inhibitDirs = ["/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/sbin", "/sys", "/usr", "/var"],
				minFree = 0 )

	def openEMCBookmarks(self):
		#TODO Use a choicebox or a LocationBox with simulated bookmarks
		self.session.openWithCallback(
			self.openBookmarksCB, 
			MovieMenu, 
				"emcBookmarks", 
				self, 
				self["list"], 
				None, 
				self["list"].makeSelectionList(), 
				self.currentPath )

	def openBookmarksCB(self, path=None):
		if path is not None:
			self.changeDir(path)

	def menuCallback(self, selection=None, parameter=None):
		if selection is not None:
			if selection == "Play last": self.playLast()
			elif selection == "playall": self.playAll()
			elif selection == "shuffleall": self.shuffleAll()
			elif selection == "Movie home": self.changeDir(config.EMC.movie_homepath.value)
			elif selection == "reload": self.initList()
			elif selection == "plugin": self.onDialogShow()
			elif selection == "setup": self.onDialogShow()
			elif selection == "ctrash": self.purgeExpired()
			elif selection == "trash": self.changeDir(config.EMC.movie_trashcan_path.value)
			elif selection == "delete": self.deleteFile(True)
			elif selection == "cutlistmarker": self.removeCutListMarker()
			elif selection == "openE2Bookmarks": self.openE2Bookmarks()
			elif selection == "removeE2Bookmark": self.deleteE2Bookmark(parameter)
			elif selection == "openEMCBookmarks": self.openEMCBookmarks()
			elif selection == "removeEMCBookmark": self.deleteEMCBookmark(parameter)
			elif selection == "dirup": self.directoryUp()
			elif selection == "oscripts": self.openScriptMenu()
			elif selection == "markall": self.markAll()
			elif selection == "updatetitle": self.updateTitle()

	def openMenu(self):
		current = self.getCurrent()
		#if not self["list"].currentSelIsPlayable(): current = None
		self.session.openWithCallback(self.menuCallback, MovieMenu, "normal", self, self["list"], current, self["list"].makeSelectionList(), self.currentPath)

	def openMenuPlugins(self):
		current = self.getCurrent()
		if self["list"].currentSelIsPlayable():
			self.session.openWithCallback(self.menuCallback, MovieMenu, "plugins", self, self["list"], current, self["list"].makeSelectionList(), self.currentPath)

	def openScriptMenu(self):
		#TODO actually not used and not working
		if self.browsingVLC():
			self.session.open(MessageBox, _("No script operation for VLC streams."), MessageBox.TYPE_ERROR)
			return
		try:
			list = []
			paths = ["/usr/lib/enigma2/python/Plugins/Extensions/EnhancedMovieCenter/script/", "/etc/enigma2/EnhancedMovieCenter/"]
			
			for path in paths:
				for e in os.listdir(path):
					pathe = os.path.join(path, e)
					if not os.path.isdir(pathe):
						if e.endswith(".sh"):
							list.append([e, pathe])
						elif e.endswith(".py"):
							list.append([e, pathe])
			
			if len(list) == 0:
				self.session.open(MessageBox, paths[0]+"\n   or" + paths[1]+"\n" + _("Does not contain any scripts."), MessageBox.TYPE_ERROR)
				return
			
			dlg = self.session.openWithCallback(self.scriptCB, ChoiceBox, " ", list)
			dlg.setTitle(_("Choose script"))
			dlg["list"].move(0,30)
		
		except Exception, e:
			emcDebugOut("[EMCMS] openScriptMenu exception:\n" + str(e))

	def markAll(self):
		for i in xrange( len (self["list"]) ):
			self["list"].toggleSelection( index=i )

	def unUsed(self):
		self.session.open(MessageBox, _("No functionality set..."), MessageBox.TYPE_INFO)

	def selectionChanged(self):
		if self.returnService:
			# Service was stored for a pending update,
			# but user wants to move, copy, delete it,
			# so we have to update returnService
			if self.tmpSelList:
				self.returnService = self.getNextSelectedService(self.getCurrent(), self.tmpSelList)
				#TODOret if self.returnService: print "EMC ret updSer " +str(self.returnService.toString())
		if self.multiSelectIdx:
			self.multiSelect( self.getCurrentIndex() )
		self.updateInfo()

	def updateInfo(self):
		self.resetInfo()
		if self.delayTimer.isActive():
			self.delayTimer.stop()
		self.delayTimer.start(int(config.EMC.movie_descdelay.value), True)
		if self.pigTimer.isActive():
			self.pigTimer.stop()
		# Movie cover
		if config.EMC.movie_pig.value == "C":
			# Show cover only for media files and directories
			if self["list"].currentSelIsPlayable() or self["list"].currentSelIsDirectory():
				self.pigTimer.start(int(config.EMC.movie_pig_delay.value), True)
		# Movie preview
		elif config.EMC.movie_pig.value == "P":
			# Play preview only if it is a video file
			if self["list"].currentSelIsPlayable():
				print "EMC: start preview"
				self.pigTimer.start(int(config.EMC.movie_pig_delay.value), True)

	def updateInfoDelayed(self):
		self.updateTitle()
		self.updateEventInfo( self.getCurrent() )

	def resetInfo(self):
		self.updateTitle()
		if self.delayTimer.isActive():
			self.delayTimer.stop()
		self.updateEventInfo(None)
		if self.pigTimer.isActive():
			self.pigTimer.stop()
		if config.EMC.movie_pig.value == "C":
			self.showCover(None)
		elif config.EMC.movie_pig.value == "P":
			# Avoid movie preview if player is running
			if self.playerInstance:
				print "EMC: reset preview"
				self.previewMovie(None)

	def showPigDelayed(self):
		if config.EMC.movie_pig.value == "C":
			self.showCover( self.getCurrent() )
		elif config.EMC.movie_pig.value == "P":
			# Avoid movie preview if player is running
			if self.playerInstance:
				self.previewMovie( self.getCurrent() )

	def updateTitle(self):
		title = ""
		if self.multiSelectIdx:
			self.setTitle(_("*** Multiselection active ***"))
			return
		
		# Display the free space
		if os.path.exists(self.currentPath):
			stat = os.statvfs(self.currentPath)
			free = (stat.f_bavail if stat.f_bavail!=0 else stat.f_bfree) * stat.f_bsize / 1024 / 1024
			if free >= 10240:	#unit in Giga bytes if more than 10 GB free
				title = "(%d GB) " %(free/1024)
			else:
				title = "(%d MB) " %(free)
		
		# Display the current path
		path = self.currentPath
		path = path.replace(config.EMC.movie_homepath.value, "...")
		# Very bad but there can be both encodings
		# E2 recordings are always in utf8
		# User files can be in cp1252
		#TODO Is there no other way?
		try:
			path.decode('utf-8')
		except UnicodeDecodeError:
			try:
				path = path.decode("cp1252").encode("utf-8")
			except UnicodeDecodeError:
				path = path.decode("iso-8859-1").encode("utf-8")
		title += path or "/"
		
		# Display the actual sorting mode
		from Plugins.Extensions.EnhancedMovieCenter.plugin import sort_modes
		sort = sort_modes.get( self["list"].getSorting() )
		if sort:
			title += " [" + str(sort[1]) + "]"
		
		# Display a permanent sort marker if it is set
		perm = self["list"].isEqualPermanentSort()
		if perm == True:
			title += _(" <P>")
		
		self.setTitle(title)

	def toggleSortMode(self):
		if self.browsingVLC(): return
		#WORKAROUND E2 doesn't send dedicated short or long pressed key events
		if self.toggle == False:
			self.toggle = True
			return
		service = self.getNextSelectedService(self.getCurrent())
		self.returnService = service
		self["list"].toggleSortingMode()
		self.initButtons()
		self.initCursor()
		self.updateInfo()

	def toggleSortOrder(self):
		if self.browsingVLC(): return
		self.toggle = False
		service = self.getNextSelectedService(self.getCurrent())
		self.returnService = service
		self["list"].toggleSortingOrder()
		self.initButtons()
		self.initCursor()
		self.updateInfo()

	def toggleSelectionList(self):
		#WORKAROUND E2 doesn't send dedicated short or long pressed key events
		if self.toggle == False:
			self.toggle = True
			return
		if self["list"].currentSelIsPlayable():
			self["list"].toggleSelection()
		# Move cursor
		if config.EMC.moviecenter_selmove.value != "o":
			if self.cursorDir == -1 and config.EMC.moviecenter_selmove.value == "b":
				self.moveToIndex( max(self.getCurrentIndex()-1, 0) )
			else:
				self.moveToIndex( min(self.getCurrentIndex()+1, len(self["list"])-1) )

	def resetSelectionList(self):
		if self.multiSelectIdx:
			self.multiSelectIdx = None
			self.updateTitle()
		self.toggle = False
		selectedlist = self["list"].makeSelectionList()[:]
		if selectedlist:
			for service in selectedlist:
				self["list"].toggleSelection(service)

	def toggleProgress(self, service=None, preparePlayback=False):
		if self.multiSelectIdx:
			self.multiSelectIdx = None
			self.updateTitle()
		if service is None:
			first = False
			forceProgress = -1
			current = self.getCurrent()
			if current is not None:
				# Force copy of selectedlist
				selectedlist = self["list"].makeSelectionList()[:]
				if len(selectedlist)>1 and not preparePlayback:
					first = True
				for sel in selectedlist:
					progress = self.__toggleProgressService(sel, preparePlayback, forceProgress, first)
					first = False
					if not preparePlayback:
						forceProgress = progress
		else:
			self.__toggleProgressService(service, preparePlayback)
	
	def __toggleProgressService(self, service, preparePlayback, forceProgress=-1, first=False):
		if service is None:
			return
		
		# Cut file handling
		path = service.getPath()
		
		# Only for compatibilty reasons
		# Should be removed anytime
		cuts  = path +".cuts"
		cutsr = path +".cutsr"
		if os.path.exists(cutsr) and not os.path.exists(cuts):
			# Rename file - to catch all old EMC revisions
			try:
				os.rename(cutsr, cuts)
			except Exception, e:
				emcDebugOut("[CUTS] Exception in __toggleProgressService: " + str(e))
		# All calculations are done in seconds
		cuts = CutList( path )
		last = cuts.getCutListLast()
		length = self["list"].getLengthOfService(service)
		progress = self["list"].getProgress(service, length=length, last=last, forceRecalc=True, cuts=cuts)
		
		if not preparePlayback:
			if first:
				if progress < 100: forceProgress = 50		# force next state 100
				else: forceProgress = 100 							# force next state 0
			if forceProgress > -1:
				progress = forceProgress
		
			if progress >= 100:
				# 100% -> 0
				# Don't care about preparePlayback, always reset to 0%
				# Save last marker
				cuts.toggleLastCutList(cuts.CUT_TOGGLE_START)
			elif progress <= 0:
				# 0% -> SAVEDLAST or length
				cuts.toggleLastCutList(cuts.CUT_TOGGLE_RESUME)
			else:
				# 1-99% -> length
				cuts.toggleLastCutList(cuts.CUT_TOGGLE_FINISHED)
		else:
			if progress >= 100 or config.EMC.movie_rewind_finished.value is True and progress >= int(config.EMC.movie_finished_percent.value):
				# 100% -> 0 or
				# Start playback and rewind is set and movie progress > finished -> 0
				# Don't save SavedMarker
				cuts.toggleLastCutList(cuts.CUT_TOGGLE_START_FOR_PLAY)
			else:
				# Delete SavedMarker
				cuts.toggleLastCutList(cuts.CUT_TOGGLE_FOR_PLAY)
		
		# Update movielist entry
		self["list"].invalidateService(service)
		return progress
	
	def IMDbSearch(self):
		name = ''
		if (self["list"].getCurrentSelName()):
			name = (self["list"].getCurrentSelName())
		try:
			from Plugins.Extensions.IMDb.plugin import IMDB
		except ImportError:
			IMDB = None
		if IMDB is not None:
			self.session.open(IMDB, name, False)

	def showEventInformation(self):
		from Screens.EventView import EventViewSimple
		from ServiceReference import ServiceReference
		
		# Get our customized event
		evt = self["list"].getCurrentEvent()
		if evt:
			self.session.open(EventViewSimple, evt, ServiceReference(self.getCurrent()))

	def initCursor(self, ifunknown=True):
		if self.returnService:
			# Move to next or last selected entry
			self.moveToService(self.returnService)
			self.returnService = None
			#TODOret if self.returnService: print "EMC ret retSer " +str(self.returnService.toString())
		
		elif self.playerInstance:
			# Get current service from movie player
			service = self.playerInstance.currentlyPlayedMovie()
			if service is not None:
				self.moveToService(service)
		
		elif ifunknown:
			# Select first entry
			#TODOret print "EMC ret initCursor movetop correct ????"
			self.moveTop()
		
		self.updateInfo()

	def onDialogShow(self):
		# Movie preview
		self.lastservice = self.lastservice or self.session.nav.getCurrentlyPlayingServiceReference()
		
		self.initButtons()
		
		if config.EMC.movie_reload.value \
			or config.EMC.needsreload.value \
			or len(self["list"]) == 0:
			config.EMC.needsreload.value = False
			DelayedFunction(50, self.initList)
		
		else:
			# Refresh is done automatically
			#self["list"].refreshList()
			self.initCursor(False)
		
		self.updateInfo()

	def onDialogHide(self):
		self.returnService = self.getCurrent() #self.getNextSelectedService(self.getCurrent(), self.tmpSelList)

	def getCurrentIndex(self):
		return self["list"].getCurrentIndex()

	def moveToIndex(self, index):
		self.multiSelectIdx = None
		self["list"].moveToIndex(index)
		self.updateInfo()
	
	def moveToService(self, service):
		self.multiSelectIdx = None
		self["list"].moveToService(service)
		self.updateInfo()

	def getNextSelectedService(self, current, selectedlist=None):
		curSerRef = None
		if current is None:
			tserRef = None
		elif not self["list"]:
			# Selectedlist is empty
			curSerRef = None
		elif selectedlist is None:
			# Selectedlist is empty
			curSerRef = current
		elif current is not None and current not in selectedlist:
			# Current is not within the selectedlist
			curSerRef = current
		else:
			# Current is within the selectedlist
			last_idx = len(self["list"]) - 1
			len_sel = len(selectedlist)
			first_sel_idx = last_idx
			last_sel_idx = 0
			
			# Get first and last selected item indexes
			for sel in selectedlist:
				idx = self["list"].getIndexOfService(sel)
				if idx < 0: idx = 0
				if idx < first_sel_idx: first_sel_idx = idx
				if idx > last_sel_idx:  last_sel_idx = idx
			
			# Calculate previous and next item indexes
			prev_idx = first_sel_idx - 1
			next_idx = last_sel_idx + 1
			len_fitola = last_sel_idx - first_sel_idx + 1
			
			# Check if there is a not selected item between the first and last selected item
			if len_fitola > len_sel:
				for entry in self["list"].list[first_sel_idx:last_sel_idx]:
					if entry[0] not in selectedlist:
						# Return first entry which is not in selectedlist
						curSerRef = entry[0]
						break
			# Check if next calculated item index is within the movie list
			elif next_idx <= last_idx:
				# Select item behind selectedlist
				curSerRef = self["list"].getServiceOfIndex(next_idx)
			# Check if previous calculated item index is within the movie list
			elif prev_idx >= 0:
				# Select item before selectedlist
				curSerRef = self["list"].getServiceOfIndex(prev_idx)
			else:
				# The whole list must be selected
				# First and last item is selected
				# Recheck and find first not selected item
				for entry in self["list"].list:
					if entry[0] not in selectedlist:
						# Return first entry which is not in selectedlist
						curSerRef = entry[0]
						break
		return curSerRef

	def loading(self, loading=True):
		self.resetInfo()
		if loading:
			self["list"].hide()
			self["wait"].setText( _("Reading directory...") )
			self["wait"].show()
		else:
			self["wait"].hide()
			self["list"].show()

	def initButtons(self):
		# Initialize buttons
		self["key_red"].text = _("Delete")
		#TODO get color from MovieCenter
		mode, order = self["list"].getSorting()
		#if order == False:
		green = ""
		#else:
		#	green = "- " # reverse
		# Display the next sorting state
		if mode == "A":
			green += _("Date sort")
		elif mode == "D":
			green += _("Alpha sort")
		self["key_green"].text = green
		self["key_yellow"].text = _("Move")
		self["key_blue"].text = _(config.EMC.movie_bluefunc.description[config.EMC.movie_bluefunc.value])

	def initList(self):
		self.initPig()
		# Initialize list
		self.reloadList()

	def triggerReloadList(self):
		#IDEA:
		# Short TV refresh list - reloads only progress
		# Long TV reload  list - finds new movies 
		self.returnService = self.getNextSelectedService(self.getCurrent(), self.tmpSelList)
		#TODOret if self.returnService: print "EMC ret triSer " +str(self.returnService.toString())
		self.reloadList()

	def reloadList(self, path=None):
		self.multiSelectIdx = None
		self.resetInfo()
		
		if config.EMC.moviecenter_loadtext.value:
			self.loading()
		DelayedFunction(20, self.__reloadList, path)

	def __reloadList(self, path):
		if path is None:
			path = self.currentPath
		
		# The try here is a nice idea, but it costs us a lot of time
		# Maybe it should be implemented with a timer
		
		#TIME t = time()
		
		#try:
		
		if self["list"].reload(path):
			self.currentPath = path
			self.initButtons()
			self.initCursor()
		
		#except Exception, e:
		#	#MAYBE: Display MessageBox
		#	emcDebugOut("[EMCMS] reloadList exception:\n" + str(e))
		#finally:
		
		if config.EMC.moviecenter_loadtext.value:
			self.loading(False)
		
		#TIME print "EMC After reload " + str(time() - t)
		
		self.updateInfo()

	#############################################################################
	# Playback functions
	#
	def setPlayerInstance(self, player):
		try:
			self.playerInstance = player
		except Exception, e:
			emcDebugOut("[EMCMS] setPlayerInstance exception:\n" + str(e))

	def openPlayer(self, playlist, playall=False):
		# Force update of event info after playing movie 
		self.resetInfo()
		
		# force a copy instead of an reference!
		self.lastPlayedMovies = playlist[:]
		playlistcopy = playlist[:]
		# Start Player
		if self.playerInstance is None:
			Notifications.AddNotification(EMCMediaCenter, playlistcopy, self, playall, self.lastservice)
		else:
			#DelayedFunction(10, self.playerInstance.movieSelected, playlist, playall)
			self.playerInstance.movieSelected(playlist, playall)
		self.busy = False
		self.close(None)

	def entrySelected(self, playall=False):
		current = self.getCurrent()
		if current is not None:
			# Save service 
			#self.returnService = self.getCurrent() #self.getNextSelectedService(self.getCurrent(), self.tmpSelList)
			
			# Think about MovieSelection should only know about directories and files
			# All other things should be in the MovieCenter
			if self["list"].currentSelIsVirtual():
				# Open folder and reload movielist
				self.setNextPath( self["list"].getCurrentSelDir() )
			elif self.browsingVLC():
				# TODO full integration of the VLC Player
				entry = self["list"].list[ self["list"].getCurrentIndex() ]
				self.vlcMovieSelected(entry)
			else:
				playlist = self["list"].makeSelectionList()
				if not self["list"].serviceMoving(playlist[0]) and not self["list"].serviceDeleting(playlist[0]):
					# Avoid starting several times in different modes
					if self.busy:
						self.busy = False
						return
					self.busy = True
					self.openPlayer(playlist, playall)
				else:
					self.session.open(MessageBox, _("File not available."), MessageBox.TYPE_ERROR, 10)

	def playLast(self):
		# Avoid starting several times in different modes
		if self.busy:
			self.busy = False
			return
		if self.multiSelectIdx:
			self.multiSelectIdx = None
			self.updateTitle()
		if self.lastPlayedMovies is None:
			self.session.open(MessageBox, _("Last played movie/playlist not available..."), MessageBox.TYPE_ERROR, 10)
		else:
			self.busy = True
			# Show a notification to indicate the Play function
			self["wait"].setText( _("Play last movie starting") )
			self["wait"].show()
			DelayedFunction(3000, self.loading, False)
			DelayedFunction(2000, self.openPlayer, self.lastPlayedMovies)

	def playAll(self):
		# Avoid starting several times in different modes
		if self.busy:
			self.busy = False
			return
		self.busy = True
		if self.multiSelectIdx:
			self.multiSelectIdx = None
			self.updateTitle()
		# Show a notification to indicate the Play function
		self["wait"].setText( _("Play All starting") )
		self["wait"].show()
		DelayedFunction(2000, self.loading, False)
		# Initialize play all
		playlist = [self.getCurrent()] 
		playall = self["list"].getNextService()
		DelayedFunction(2000, self.openPlayer, playlist, playall)

	def shuffleAll(self):
		# Avoid starting several times in different modes
		if self.busy:
			self.busy = False
			return
		self.busy = True
		if self.multiSelectIdx:
			self.multiSelectIdx = None
			self.updateTitle()
		# Show a notification to indicate the Shuffle function
		self["wait"].setText( _("Shuffle All starting") )
		self["wait"].show()
		DelayedFunction(2000, self.loading, False)
		# Initialize shuffle all
		playlist = [self.getCurrent()] 
		shuffleall = self["list"].getRandomService()
		DelayedFunction(2000, self.openPlayer, playlist, shuffleall)

	def lastPlayedCheck(self, service):
		try:
			if self.lastPlayedMovies is not None:
				if service in self.lastPlayedMovies:
					self.lastPlayedMovies.remove(service)
				if len(self.lastPlayedMovies) == 0:
					self.lastPlayedMovies = None
		except Exception, e:
			emcDebugOut("[EMCMS] lastPlayedCheck exception:\n" + str(e))

	#############################################################################
	# Record control functions
	#
	def isRecording(self, service):
		path = service.getPath()
		if path:
			return self["list"].recControl.isRecording(path)
		else:
			return False

	def getRecordingService(self, service):
		path = service.getPath()
		if path:
			return self["list"].recControl.getRecordingService(path)
		else:
			return False

	def getRecordingTimes(self, service):
		path = service.getPath()
		if path:
			return self["list"].recControl.getRecordingTimes(path)
		else:
			return False

	def stopRecordConfirmation(self, confirmed):
		if not confirmed: return
		# send as a list?
		stoppedAll=True
		for e in self.recsToStop:
			stoppedAll = stoppedAll and self["list"].recControl.stopRecording(e)
		if not stoppedAll:
			self.session.open(MessageBox, _("Not stopping any repeating timers. Modify them with the timer editor."), MessageBox.TYPE_INFO, 10)

	def stopRecordQ(self):
		try:
			filenames = ""
			for e in self.recsToStop:
				filenames += "\n" + e.split("/")[-1][:-3]
			self.session.openWithCallback(self.stopRecordConfirmation, MessageBox, _("Stop ongoing recording?\n") + filenames, MessageBox.TYPE_YESNO)
		except Exception, e:
			emcDebugOut("[EMCMS] stopRecordQ exception:\n" + str(e))

	def moveRecCheck(self, service, targetPath):
		try:
			path = service.getPath()
			if self["list"].recControl.isRecording(path):
				self["list"].recControl.fixTimerPath(path, path.replace(self.currentPath, targetPath))
		except Exception, e:
			emcDebugOut("[EMCMS] moveRecCheck exception:\n" + str(e))

	#############################################################################
	# File IO functions
	#TODO Move all file operation functions to a separate class
	#
	def removeCutListMarker(self):
		if self.browsingVLC(): return
		current = self.getCurrent()	# make sure there is atleast one entry in the list
		if current is not None:
			selectedlist = self["list"].makeSelectionList()[:]
			for service in selectedlist:
				cuts = CutList( service.getPath() )
				cuts.removeMarksCutList()
				self["list"].unselectService(service)
			emcDebugOut("[EMCMS] cut list marker removed permanently")

	def mountpoint(self, path, first=True):
		if first: path = os.path.realpath(path)
		if os.path.ismount(path) or len(path)==0: return path
		return self.mountpoint(os.path.dirname(path), False)

	def deleteFile(self, permanently=False):
		if self.multiSelectIdx:
			self.multiSelectIdx = None
			self.updateTitle()
		if self.browsingVLC(): return
		self.permanentDel  = permanently or not config.EMC.movie_trashcan_enable.value
		self.permanentDel |= self.currentPath == config.EMC.movie_trashcan_path.value
		self.permanentDel |= self.mountpoint(self.currentPath) != self.mountpoint(config.EMC.movie_trashcan_path.value)
		current = self.getCurrent()	# make sure there is atleast one entry in the list
		if current is not None:
			selectedlist = self["list"].makeSelectionList()[:]
			single = len(selectedlist) == 1 and current==selectedlist[0]
			if single and self["list"].currentSelIsDirectory():
				if not config.EMC.movie_trashcan_enable.value or config.EMC.movie_delete_validation.value or self.permanentDel:
					path = current.getPath()
					if os.path.islink(path):
						msg = _("Do you really want to remove your link\n%s?") % (path)
					else:
						msg = _("Do you really want to remove your directory\n%s?") % (path)
					self.session.openWithCallback(
							boundFunction(self.delPathSelConfirmed, current),
							MessageBox,
							msg )
				else:
					self.delPathSelConfirmed(current, True)
			
			elif single and self["list"].currentSelIsE2Bookmark():
				# Delete a single E2 bookmark
				self.deleteE2Bookmark(current)
			elif single and self["list"].currentSelIsEMCBookmark():
				# Delete a single EMC bookmark
				self.deleteEMCBookmark(current)
			
			else:
				if self["list"].serviceBusy(selectedlist[0]): return
				if selectedlist and len(selectedlist)>0:
					self.recsToStop = []
					self.remRecsToStop = False
					for service in selectedlist:
						path = service.getPath()
						if self["list"].recControl.isRecording(path):
							self.recsToStop.append(path)
						if config.EMC.remote_recordings.value and self["list"].recControl.isRemoteRecording(path):
							self.remRecsToStop = True
					if len(self.recsToStop)>0:
						self.stopRecordQ()
					else:
						self.deleteMovieQ(selectedlist, self.remRecsToStop)

	def deleteE2Bookmark(self, service):
		if service:
			path = service.getPath()
			if self.isE2Bookmark(path):
				if config.EMC.movie_delete_validation.value:
					self.session.openWithCallback(
							boundFunction(self.deleteE2BookmarkConfirmed, service),
							MessageBox,
							_("Do you really want to remove your bookmark\n%s?") % (path) )
				else:
					self.deleteE2BookmarkConfirmed(service, True)

	def deleteE2BookmarkConfirmed(self, service, confirm):
		if confirm and service and config.movielist and config.movielist.videodirs:
			path = service.getPath()
			if self.removeE2Bookmark(path):
				# If service is not in list, don't care about it.
				print "EMC: deleteEMCBookmarkConfirmed"
				print service
				print self.getCurrent()
				print self.returnService
				self["list"].removeServiceOfType(service, cmtBME2)
				print service
				print self.getCurrent()
				print self.returnService

	def deleteEMCBookmark(self, service):
		if service:
			path = service.getPath()
			if self.isEMCBookmark(path):
				if config.EMC.movie_delete_validation.value:
					self.session.openWithCallback(
							boundFunction(self.deleteEMCBookmarkConfirmed, service),
							MessageBox,
							_("Do you really want to remove your bookmark\n%s?") % (path) )
				else:
					self.deleteEMCBookmarkConfirmed(service, True)

	def deleteEMCBookmarkConfirmed(self, service, confirm):
		if confirm and service:
			path = service.getPath()
			if self.removeEMCBookmark(path):
				# If service is not in list, don't care about it.
				print "EMC: deleteEMCBookmarkConfirmed"
				print service
				print self.getCurrent()
				print self.returnService
				self["list"].removeServiceOfType(service, cmtBMEMC)
				print service
				print self.getCurrent()
				print self.returnService

	def deleteMovieQ(self, selectedlist, remoteRec):
		try:
			self.tmpSelList = selectedlist[:]
			self.delCurrentlyPlaying = False
			rm_add = ""
			if remoteRec:
				rm_add = _(" Deleting remotely recorded and it will display an rec-error dialog on the other DB.") + "\n"
				
			if self.playerInstance is not None:
				if self.playerInstance.currentlyPlayedMovie() in selectedlist:
					self.delCurrentlyPlaying = True
			entrycount = len(selectedlist)
			delStr = _("Delete") + _(" permanently")*self.permanentDel
			if entrycount == 1:
				service = selectedlist[0]
				name = self["list"].getNameOfService(service)
				if not self.delCurrentlyPlaying:
					if not config.EMC.movie_trashcan_enable.value or config.EMC.movie_delete_validation.value or self.permanentDel:
						self.session.openWithCallback(
								self.deleteMovieConfimation,
								MessageBox,
								delStr + "?\n" + rm_add + name,
								MessageBox.TYPE_YESNO )
					else:
						self.deleteMovieConfimation(True)
				else:
					self.session.openWithCallback(
							self.deleteMovieConfimation,
							MessageBox,
							delStr + _(" currently played?") + "\n" + rm_add + name,
							MessageBox.TYPE_YESNO )
			else:
				if entrycount > 1:
					movienames = ""
					i = 0
					for service in selectedlist:
						if i >= 5 and entrycount > 5:	# show only 5 entries in the file list
							movienames += "..."
							break
						i += 1
						name = self["list"].getNameOfService(service)
						if len(name) > 48:
							name = name[:48] + "..."	# limit the name string
						movienames += name + "\n"*(i<entrycount)
					if not self.delCurrentlyPlaying:
						if not config.EMC.movie_trashcan_enable.value or config.EMC.movie_delete_validation.value or self.permanentDel:
							self.session.openWithCallback(
									self.deleteMovieConfimation,
									MessageBox,
									delStr + _(" all selected video files?") + "\n" + rm_add + movienames,
									MessageBox.TYPE_YESNO )
						else:
							self.deleteMovieConfimation(True)
					else:
						self.session.openWithCallback(self.deleteMovieConfimation, MessageBox, delStr + _(" all selected video files? The currently playing movie is also one of the selections and its playback will be stopped.") + "\n" + rm_add + movienames, MessageBox.TYPE_YESNO)
		except Exception, e:
			self.session.open(MessageBox, _("Delete error:\n") + str(e), MessageBox.TYPE_ERROR)
			emcDebugOut("[EMCMS] deleteMovieQ exception:\n" + str(e))

	def deleteMovieConfimation(self, confirmed):
		current = self.getCurrent()
		if confirmed and self.tmpSelList is not None and len(self.tmpSelList)>0:
			if self.delCurrentlyPlaying:
				if self.playerInstance is not None:
					self.playerInstance.removeFromPlaylist(self.tmpSelList)
			delete = not config.EMC.movie_trashcan_enable.value or self.permanentDel
			if os.path.exists(config.EMC.movie_trashcan_path.value) or delete:
				# if the user doesn't want to keep the movies in the trash, purge immediately
				self.execFileOp(config.EMC.movie_trashcan_path.value, current, self.tmpSelList, op="delete", purgeTrash=delete)
				for x in self.tmpSelList:
					self.lastPlayedCheck(x)
				self["list"].resetSelection()
			elif not delete:
				self.session.openWithCallback(self.trashcanCreate, MessageBox, _("Delete failed because the trashcan directory does not exist. Attempt to create it now?"), MessageBox.TYPE_YESNO)
			emcDebugOut("[EMCMS] deleteMovie")

	def delPathSelConfirmed(self, service, confirm):
		if confirm and service:
			path = service.getPath()
			if path != "..":
				if os.path.islink(path):
					emcTasker.shellExecute("rm -f '" + path + "'")
					self["list"].removeService(service)
				elif os.path.exists(path):
					if len(os.listdir(path))>0:
						self.session.open(MessageBox, _("Directory is not empty."), MessageBox.TYPE_ERROR, 10)
					else:
						emcTasker.shellExecute('rmdir "' + path +'"')
						self["list"].removeService(service)
			else:
				self.session.open(MessageBox, _("Cannot delete the parent directory."), MessageBox.TYPE_ERROR, 10)

	def scriptCB(self, result=None):
		if result is None: return
		
		env = "export EMC_OUTDIR=%s"%config.EMC.folder.value
		env += " EMC_HOME=%s"%config.EMC.movie_homepath.value
		env += " EMC_PATH_LIMIT=%s"%config.EMC.movie_pathlimit.value
		env += " EMC_TRASH=%s"%config.EMC.movie_trashcan_path.value
		env += " EMC_TRASH_DAYS=%s"%int(config.EMC.movie_trashcan_limit.value)
		
		if self["list"].currentSelIsPlayable() or self["list"].currentSelIsDirectory():
			current = self["list"].getCurrentSelDir() + (self["list"].currentSelIsDirectory()) * "/"
			current = current.replace(" ","\ ")
			if os.path.exists(result[1]):
				if result[1].endswith(".sh"):
					emcTasker.shellExecute("%s; sh %s %s %s" %(env, result[1], self.currentPath, current))
				elif result[1].endswith(".py"):
					emcTasker.shellExecute("%s; python %s %s %s" %(env, result[1], self.currentPath, current))

	def moveCB(self, service):
		self["list"].highlightService(False, "move", service)	# remove the highlight
		if not config.EMC.movie_hide_mov.value:
			self["list"].removeService(service)
		self.updateInfo()

	def delCB(self, service):
		self["list"].highlightService(False, "del", service)	# remove the highlight
		if not config.EMC.movie_hide_del.value:
			self["list"].removeService(service)
		self.updateInfo()

	def copyCB(self, service):
		self["list"].highlightService(False, "copy", service)	# remove the highlight
		self["list"].invalidateService(service)
		self.updateInfo()

#Think about: All file operations should be in a separate file

	def execFileOp(self, targetPath, current, selectedlist, op="move", purgeTrash=False):
		self.returnService = self.getNextSelectedService(current, selectedlist)
		cmd = []
		association = []
		for service in selectedlist:
			path = os.path.splitext( self["list"].getFilePathOfService(service) )[0]
			if path is not None:
				if op=="delete":	# target == trashcan
					c = []
					if purgeTrash or self.currentPath == targetPath or self.mountpoint(self.currentPath) != self.mountpoint(targetPath):
						# direct delete from the trashcan or network mount (no copy to trashcan from different mountpoint)
						c.append( 'rm -f "'+ path +'."*' )
					else:
						# create a time stamp with touch
						c.append( 'touch "'+ path +'."*' )
						# move movie into the trashcan
						c.append( 'mv "'+ path +'."* "'+ targetPath +'/"' )
					cmd.append( c )
					association.append( (self.delCB, service) )	# put in a callback for this particular movie
					self["list"].highlightService(True, "del", service)
					if config.EMC.movie_hide_del.value:
						self["list"].removeService(service)
				elif op == "move":
					c = []
					#if self.mountpoint(self.currentPath) == self.mountpoint(targetPath):
					#	#self["list"].removeService(service)	# normal direct move
					#	pass
					#else:
					# different self.mountpoint? -> reset user&group
					if self.mountpoint(targetPath) != self.mountpoint(config.EMC.movie_homepath.value):		# CIFS to HDD is ok!
						# need to change file ownership to match target filesystem file creation
						tfile = targetPath + "/owner_test"
						sfile = "\""+ path +".\"*"
						c.append( "touch %s;ls -l %s | while read flags i owner group crap;do chown $owner:$group %s;done;rm %s" %(tfile,tfile,sfile,tfile) )
					c.append( 'mv "'+ path +'."* "'+ targetPath +'/"' )
					cmd.append( c )
					association.append( (self.moveCB, service) )	# put in a callback for this particular movie
					self["list"].highlightService(True, "move", service)
					if config.EMC.movie_hide_mov.value:
						self["list"].removeService(service)
					self.moveRecCheck(service, targetPath)
				elif op == "copy":
					c = []
					#if self.mountpoint(self.currentPath) == self.mountpoint(targetPath):
					#	#self["list"].removeService(service)	# normal direct move
					#	pass
					#else:
					# different self.mountpoint? -> reset user&group
					if self.mountpoint(targetPath) != self.mountpoint(config.EMC.movie_homepath.value):		# CIFS to HDD is ok!
						# need to change file ownership to match target filesystem file creation
						tfile = targetPath + "/owner_test"
						sfile = "\""+ path +".\"*"
						c.append( "touch %s;ls -l %s | while read flags i owner group crap;do chown $owner:$group %s;done;rm %s" %(tfile,tfile,sfile,tfile) )
					c.append( 'cp "'+ path +'."* "'+ targetPath +'/"' )
					cmd.append( c )
					association.append( (self.copyCB, service) )	# put in a callback for this particular movie
					self["list"].highlightService(True, "copy", service)
					#if config.EMC.movie_hide_mov.value:
					#	self["list"].removeService(service)
				self.lastPlayedCheck(service)
		self["list"].resetSelection()
		if cmd:
			association.append((self.initCursor, False)) # Set new Cursor position
			association.append((self.postFileOp))
			# Sync = True: Run script for one file do association and continue with next file
			emcTasker.shellExecute(cmd, association, True)	# first move, then delete if expiration limit is 0

	def postFileOp(self):
		self.tmpSelList = None

	def moveMovie(self):
		# Avoid starting move and copy at the same time
		#WORKAROUND E2 doesn't send dedicated short or long pressed key events
		if self.move == False:
			self.move = True
			return
		if self.multiSelectIdx:
			self.multiSelectIdx = None
			self.updateTitle()
		if self.browsingVLC() or self["list"].getCurrentSelDir() == "VLC servers": return
		current = self.getCurrent()
		if current is not None:
			selectedlist = self["list"].makeSelectionList()
			dialog = False
			if self["list"].currentSelIsDirectory():
				if current != selectedlist[0]:	# first selection != cursor pos?
					targetPath = self.currentPath
					if self["list"].getCurrentSelDir() == "..":
						targetPath = os.path.dirname(targetPath)
					else:
						#targetPath += "/" + self["list"].getCurrentSelDir()
						targetPath = self["list"].getCurrentSelDir()
					self.tmpSelList = selectedlist[:]
					self.execFileOp(targetPath, current, self.tmpSelList)
					self["list"].resetSelection()
				else:
					if len(selectedlist) == 1:
						self.session.open(MessageBox, _("How to move files:\nSelect some movies with the VIDEO-button, move the cursor on top of the destination directory and press yellow."), MessageBox.TYPE_ERROR, 10)
					else:
						dialog = True
			else:
				dialog = True
			if dialog:
				try:
					if len(selectedlist)==1 and self["list"].serviceBusy(selectedlist[0]): return
					self.tmpSelList = selectedlist[:]
					self.session.openWithCallback(
						self.mvDirSelected,
						LocationBox,
							windowTitle = _("Move file(s):"),
							text = _("Choose directory"),
							currDir = str(self.currentPath)+"/",
							bookmarks = config.movielist.videodirs,
							autoAdd = False,
							editDir = True,
							inhibitDirs = ["/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/sbin", "/sys", "/usr", "/var"],
							minFree = 100 )
				except:
					self.session.open(MessageBox, _("How to move files:\nSelect some movies with the VIDEO-button, move the cursor on top of the destination directory and press yellow."), MessageBox.TYPE_ERROR, 10)
			emcDebugOut("[EMCMS] moveMovie")

	def mvDirSelected(self, targetPath):
		if targetPath is not None:
			current = self.getCurrent()
			self.execFileOp(targetPath, current, self.tmpSelList)
			emcDebugOut("[EMCMS] mvDirSelected")

	def copyMovie(self):
		# Avoid starting move and copy at the same time
		self.move = False
		if self.multiSelectIdx:
			self.multiSelectIdx = None
			self.updateTitle()
		if self.browsingVLC() or self["list"].getCurrentSelDir() == "VLC servers": return
		current = self.getCurrent()
		if current is not None:
			selectedlist = self["list"].makeSelectionList()
			dialog = False
			if self["list"].currentSelIsDirectory():
				if current != selectedlist[0]:	# first selection != cursor pos?
					targetPath = self.currentPath
					if self["list"].getCurrentSelDir() == "..":
						targetPath = os.path.dirname(targetPath)
					else:
						#targetPath += "/" + self["list"].getCurrentSelDir()
						targetPath = self["list"].getCurrentSelDir()
					self.tmpSelList = selectedlist[:]
					self.execFileOp(targetPath, current, self.tmpSelList, op="copy")
					self["list"].resetSelection()
				else:
					if len(selectedlist) == 1:
						self.session.open(MessageBox, _("How to copy files:\nSelect some movies with the VIDEO-button, move the cursor on top of the destination directory and press yellow long."), MessageBox.TYPE_ERROR, 10)
					else:
						dialog = True
			else:
				dialog = True
			if dialog:
				try:
					if len(selectedlist)==1 and self["list"].serviceBusy(selectedlist[0]): return
					self.tmpSelList = selectedlist[:]
					self.session.openWithCallback(
						self.cpDirSelected,
						LocationBox,
							windowTitle = _("Copy file(s):"),
							text = _("Choose directory"),
							currDir = str(self.currentPath)+"/",
							bookmarks = config.movielist.videodirs,
							autoAdd = False,
							editDir = True,
							inhibitDirs = ["/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/sbin", "/sys", "/usr", "/var"],
							minFree = 100 )
				except:
					self.session.open(MessageBox, _("How to copy files:\nSelect some movies with the VIDEO-button, move the cursor on top of the destination directory and press yellow long."), MessageBox.TYPE_ERROR, 10)
			emcDebugOut("[EMCMS] copyMovie")

	def cpDirSelected(self, targetPath):
		if targetPath is not None:
			current = self.getCurrent()
			self.execFileOp(targetPath, current, self.tmpSelList, op="copy")
			emcDebugOut("[EMCMS] cpDirSelected")

	def trashcanCreate(self, confirmed):
		try:
			os.makedirs(config.EMC.movie_trashcan_path.value)
			if self.currentPath == os.path.dirname(config.EMC.movie_trashcan_path.value):
				# reload to show the trashcan only if the current path will contain the trashcan
				self.reloadList()
		except Exception, e:
			self.session.open(MessageBox, _("Trashcan create failed. Check mounts and permissions."), MessageBox.TYPE_ERROR)
			emcDebugOut("[EMCMS] trashcanCreate exception:\n" + str(e))

	# Move all trashcan operations to a separate class
	def purgeExpired(self):
		try:
			movie_trashpath = config.EMC.movie_trashcan_path.value
			movie_homepath = config.EMC.movie_homepath.value
			if os.path.exists(movie_trashpath):
				if config.EMC.movie_trashcan_clean.value is True:
					# Trashcan cleanup
					purgeCmd = ""
					for root, dirs, files in os.walk(movie_trashpath):
						for movie in files:
							# Only check media files
							ext = os.path.splitext(movie)[1].lower()
							if ext in extMedia:
								fullpath = os.path.join(root, movie)
								currTime = localtime()
								if os.path.exists(fullpath):
									expTime = localtime(os.stat(fullpath).st_mtime + 24*60*60*int(config.EMC.movie_trashcan_limit.value))
									if currTime > expTime:
										purgeCmd += '; rm -f "'+ os.path.splitext(fullpath)[0] +'."*'
					if purgeCmd != "":
						emcTasker.shellExecute(purgeCmd[2:])
						emcDebugOut("[EMCMS] trashcan cleanup activated")
					else:
						emcDebugOut("[EMCMS] trashcan cleanup: nothing to delete...")
				if config.EMC.movie_finished_clean.value is True:
					#TODO very slow
					# Movie folder cleanup
					# Start only if dreambox is in standby
					# No subdirectory handling
					import Screens.Standby
					if Screens.Standby.inStandby:
						mvCmd = ""
						for root, dirs, files in os.walk(movie_homepath):
							if root.startswith(movie_trashpath):
								# Don't handle the trashcan and its subfolders
								continue
							for movie in files:
								
								# Only check media files
								ext = os.path.splitext(movie)[1].lower()
								if ext in extMedia:
									fullpath = os.path.join(root, movie)
									fullpathcuts = fullpath + ".cuts"
									if os.path.exists(fullpathcuts):
										currTime = localtime()
										expTime = localtime(os.stat(fullpathcuts).st_mtime + 24*60*60*int(config.EMC.movie_finished_limit.value))
										if currTime > expTime:
											# Check progress
											service = self["list"].getPlayerService(fullpath, movie, ext)
											progress = self["list"].getProgress(service, forceRecalc=True)
											if progress >= int(config.EMC.movie_finished_percent.value):
												# cut file extension
												fullpath = os.path.splitext(fullpath)[0]
												# create a time stamp with touch for all corresponding files
												mvCmd += '; touch "'+ fullpath +'."*'
												# move movie into the trashcan
												mvCmd += '; mv "'+ fullpath +'."* "'+ movie_trashpath +'"'
						if mvCmd != "":
							association = []
							association.append((self.reloadList))	# Force list reload after cleaning
							emcTasker.shellExecute(mvCmd[2:], association)
							emcDebugOut("[EMCMS] finished movie cleanup activated")
						else:
							emcDebugOut("[EMCMS] finished movie cleanup: nothing to move...")
			else:
				emcDebugOut("[EMCMS] trashcan cleanup: no trashcan...")
		except Exception, e:
			emcDebugOut("[EMCMS] purgeExpired exception:\n" + str(e))
