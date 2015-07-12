import os
import difflib

import sublime
import sublime_plugin


class EraseViewCommand( sublime_plugin.TextCommand ):
	def run( self, edit ):
		self.view.erase( edit, sublime.Region( 0, self.view.size() ) )

class InsertViewCommand( sublime_plugin.TextCommand ):
	def run( self, edit, string='' ):
		self.view.insert( edit, self.view.size(), string )
		
sbs_markedSelection = [ '', '' ]
class SbsMarkSelCommand( sublime_plugin.TextCommand ):
	def run( self, edit, string='' ):
		global sbs_markedSelection
		
		window = sublime.active_window()
		view = window.active_view()
		sel = view.sel()

		region = sel[0]
		selectionText = view.substr( region )
		
		sbs_markedSelection[0] = sbs_markedSelection[1]
		sbs_markedSelection[1] = selectionText

class SbsCompareCommand( sublime_plugin.TextCommand ):	
	def settings( self ):
		return sublime.load_settings( 'SBSCompare.sublime-settings' )
		
	def get_view_contents( self, view ):
		selection = sublime.Region( 0, view.size() )
		content = view.substr( selection )
		return content
		
	def highlight_lines( self, view, lines, col ):
		regionList = []
		for num in lines:
			point = view.text_point( num, 0 )
			regionList.append( view.line( point ) )
			
		colour = 'keyword'
		if col == 'A':
			colour = self.settings().get( 'remove_colour', 'invalid.illegal' )
		elif col == 'B':
			colour = self.settings().get( 'add_colour', 'string' )

		# fill highlighting (DRAW_NO_OUTLINE) only exists on ST3+
		drawType = sublime.DRAW_OUTLINED
		if int( sublime.version() ) >= 3000:
			if not self.settings().get( 'outlines_only', False ):
				drawType = sublime.DRAW_NO_OUTLINE
			
		view.add_regions( 'diff_highlighted', regionList, colour, '', drawType )
				
		
	def compare_views( self, view1, view2 ):
		view1_contents = self.get_view_contents( view1 )
		view2_contents = self.get_view_contents( view2 )
		
		linesA = view1_contents.splitlines( False )
		linesB = view2_contents.splitlines( False )
		
		bufferA = []
		bufferB = []
		
		highlightA = []
		highlightB = []
		
		diff = difflib.ndiff( linesA, linesB )	
			
		lineNum = 0
		for line in diff:
			lineNum += 1
			code = line[:2]
			text = line[2:]
			
			if code == '- ':
				bufferA.append( text )
				bufferB.append( '' )
				highlightA.append( lineNum - 1 )
			elif code == '+ ':
				bufferA.append( '' )
				bufferB.append( text )
				highlightB.append( lineNum - 1 )
			elif code == '  ':
				bufferA.append( text )
				bufferB.append( text )
			else:
				lineNum -= 1
									
						
		window = sublime.active_window()
		
		window.focus_view( view1 )
		window.run_command( 'erase_view' )
		window.run_command( 'insert_view', { 'string': '\n'.join( bufferA ) } )
		self.highlight_lines( view1, highlightA, 'A' )
		
		window.focus_view( view2 )
		window.run_command( 'erase_view' )
		window.run_command( 'insert_view', { 'string': '\n'.join( bufferB ) } )
		self.highlight_lines( view2, highlightB, 'B' )
		
		if self.settings().get( 'line_count_popup', False ):
			numDiffs = len( highlightA ) + len( highlightB )
			sublime.message_dialog( str( len( highlightA ) ) + ' lines removed, ' + str( len( highlightB ) ) + ' lines added\n' + str( numDiffs ) + ' line differences total' )

		
	def run( self, edit, with_active = False, group = -1, index = -1, compare_selections = False ):		
		global sbs_markedSelection
		
		active_view = self.view
		active_window = active_view.window()
		active_id = active_view.id()
		
		openTabs = []
		
		for view in active_window.views():
			if view.id() != active_id:
				viewName = 'untitled'
				if view.file_name():
					viewName = view.file_name()
				elif view.name():
					viewName = view.name()
				openTabs.append( [ viewName, view ] )

		def create_comparison( view1_contents, view2_contents, syntax, name1_override = False, name2_override = False ):
			view1_syntax = syntax
			view2_syntax = syntax
			
			# make new window
			active_window.run_command( 'new_window' )		
			new_window = sublime.active_window()
			new_window.set_layout( { "cols": [0.0, 0.5, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1], [1, 0, 2, 1]] } )
			
			if self.settings().get( 'toggle_sidebar', False ):
				new_window.run_command( 'toggle_side_bar' )
			if self.settings().get( 'toggle_menu', False ):
				new_window.run_command( 'toggle_menu' )
			
			# view 1
			new_window.run_command( 'new_file' )
			new_window.run_command( 'insert_view', { 'string': view1_contents } )
			new_window.active_view().set_syntax_file( view1_syntax )
			
			view1_name = 'untitled'
			if active_view.file_name():
				view1_name = active_view.file_name()
			elif active_view.name():
				view1_name = active_view.name()
			if name1_override != False:
				view1_name = name1_override
			new_window.active_view().set_name( os.path.basename( view1_name ) + ' (active)' )
				
			new_window.active_view().set_scratch( True )	
			view1 = new_window.active_view()
			
			# view 2
			new_window.run_command( 'new_file' )
			new_window.run_command( 'insert_view', { 'string': view2_contents } )
			new_window.active_view().set_syntax_file( view2_syntax )
			new_window.active_view().set_name( os.path.basename( name2_override ) + ' (other)' )
			
			# move view 2 to group 2
			new_window.set_view_index( new_window.active_view(), 1, 0 )
			
			new_window.active_view().set_scratch( True )
			view2 = new_window.active_view()
			
			# run diff
			self.compare_views( view1, view2 )
			
			# make readonly
			new_window.focus_view( view1 )
			if self.settings().get( 'read_only', False ):
				new_window.active_view().set_read_only( True )
				
			new_window.focus_view( view2 )
			if self.settings().get( 'read_only', False ):
				new_window.active_view().set_read_only( True )
			
			# activate scroll syncer				
			ViewScrollSyncer( new_window, [ view1, view2 ] )
			
			# move views to top left
			view1.set_viewport_position( (0, 0), False )
			view2.set_viewport_position( (0, 0), False )

		def on_click( index ):
			if index > -1:
				# get original views' data
				view1_contents = self.get_view_contents( active_view )
				view2_contents = self.get_view_contents( openTabs[index][1] )
				
				syntax = active_view.settings().get( 'syntax' )
				
				create_comparison( view1_contents, view2_contents, syntax, False, openTabs[index][0] )

		if compare_selections == True:
			selA = sbs_markedSelection[0]
			selB = sbs_markedSelection[1]
			
			sel = active_view.sel()
			
			selNum = 0
			for selection in sel:
				selNum += 1
			
			if selNum == 2:
				selA = active_view.substr( sel[0] )
				selB = active_view.substr( sel[1] )
			
			syntax = active_view.settings().get( 'syntax' )
			create_comparison( selA, selB, syntax, 'selection A', 'selection B' )
		elif len( openTabs ) == 1:
			on_click( 0 )
		else:
			if with_active == True:
				active_group, active_group_index = active_window.get_view_index( active_view )
				
				if index > active_group_index:
					index -= 1
					
				on_click( index )	
			else:
				menu_items = []
				for tab in openTabs:
					fileName = tab[0]
					if self.settings().get( 'expanded_filenames', False ):
						menu_items.append( [ os.path.basename( fileName ), fileName ] )
					else:
						menu_items.append( os.path.basename( fileName ) )	
				sublime.set_timeout( self.view.window().show_quick_panel( menu_items, on_click ) )


class ViewScrollSyncer( object ):
	def __init__( self, window, viewList ):
		self.window = window
		self.views = viewList
		self.timeout_focused = 10
		self.timeout_unfocused = 50
		
		self.run()
		
	def update_scroll( self, view1, view2, lastUpdated ):
		if lastUpdated == 'A':
			view2.set_viewport_position( view1.viewport_position(), False )
		elif lastUpdated == 'B':
			view1.set_viewport_position( view2.viewport_position(), False )
		
	def run( self ):
		if not self.window:
			return
		
		if self.window.id() != sublime.active_window().id():
			sublime.set_timeout( self.run, self.timeout_unfocused )
			return
			
		view1 = self.views[0]
		view2 = self.views[1]
		
		if not view1 or not view2:
			return
		
		vecA = view1.viewport_position()
		vecB = view2.viewport_position()
		
		if vecA != vecB:
			lastVecA0 = view1.settings().get( 'viewsync_last_vec0', 1 )
			lastVecA1 = view1.settings().get( 'viewsync_last_vec1', 1 )
			
			lastVecB0 = view2.settings().get( 'viewsync_last_vec0', 1 )
			lastVecB1 = view2.settings().get( 'viewsync_last_vec1', 1 )
			
			lastVecA = ( lastVecA0, lastVecA1 )
			lastVecB = ( lastVecB0, lastVecB1 )
			
			lastUpdated = ''
			
			if lastVecA != vecA:				
				lastUpdated = 'A'
				
				view1.settings().set( 'viewsync_last_vec0', vecA[0] )
				view1.settings().set( 'viewsync_last_vec1', vecA[1] )
				
				view2.settings().set( 'viewsync_last_vec0', vecA[0] )
				view2.settings().set( 'viewsync_last_vec1', vecA[1] )				
				
			if lastVecB != vecB:				
				lastUpdated = 'B'
				
				view1.settings().set( 'viewsync_last_vec0', vecB[0] )
				view1.settings().set( 'viewsync_last_vec1', vecB[1] )
				
				view2.settings().set( 'viewsync_last_vec0', vecB[0] )
				view2.settings().set( 'viewsync_last_vec1', vecB[1] )
				
			if ( lastUpdated != '' ):
				self.update_scroll( view1, view2, lastUpdated )
		
		sublime.set_timeout( self.run, self.timeout_focused )