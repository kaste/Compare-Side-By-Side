from __future__ import annotations
from collections import deque
import difflib
from functools import partial
from itertools import chain, tee
import os
import re
import threading

import sublime
import sublime_plugin

from typing import Iterable, TypeVar
T = TypeVar("T")


# (c) @rhettinger on GitHub
def triplewise(iterable: Iterable[T]) -> Iterable[tuple[T, T, T]]:
    """Return overlapping triplets from *iterable*.

    >>> list(triplewise('ABCDE'))
    [('A', 'B', 'C'), ('B', 'C', 'D'), ('C', 'D', 'E')]

    """
    # This deviates from the itertools documentation reciple - see
    # https://github.com/more-itertools/more-itertools/issues/889
    t1, t2, t3 = tee(iterable, 3)
    next(t3, None)
    next(t3, None)
    next(t2, None)
    return zip(t1, t2, t3)


def sbs_settings():
    return sublime.load_settings('SBSCompare.sublime-settings')


class sbs_replace_view_contents(sublime_plugin.TextCommand):
    def run(self, edit, text):
        view = self.view
        view.set_read_only(False)
        view.replace(edit, sublime.Region(0, view.size()), text)
        view.set_read_only(True)


class SbsLayoutPreserver(sublime_plugin.EventListener):
    def count_views(self, ignore=None):
        numCompare = 0
        numNotCompare = 0
        nonCompareWin = None
        for w in sublime.windows():
            for v in w.views():
                if ignore and v.id() == ignore:
                    continue
                if v.settings().get('is_sbs_compare'):
                    numCompare += 1
                else:
                    numNotCompare += 1
                    nonCompareWin = w
            if len(w.views()) == 0:
                nonCompareWin = w
        return {
            'compare': numCompare,
            'notCompare': numNotCompare,
            'nonCompareWin': nonCompareWin,
        }

    def on_pre_close(self, view):
        # if one comparison view is closed, close the other
        if view.settings().get('is_sbs_compare'):
            win = view.window()
            sublime.set_timeout(lambda: win.run_command('close_window'), 10)
            return

        # if there are no non-comparison views open after this closes...
        count = self.count_views(ignore=view.id())
        if count['compare'] > 0 and count['notCompare'] == 0:
            last_file = view.file_name()

            # wait until the view is closed, then check again
            def after_close():
                # if there's no non-comparison window still open, make a new one
                # (there will be if the user only closes a tab!)
                count = self.count_views()
                if count['nonCompareWin'] is None:
                    sublime.active_window().run_command('new_window')
                    win = sublime.active_window()

                    # reopen last file
                    if last_file is not None:
                        win.open_file(last_file)

                    sublime.set_timeout(
                        lambda: win.show_quick_panel(
                            ['Please close all comparison windows first'], None
                        ),
                        10,
                    )

            sublime.set_timeout(after_close, 100)


sbs_markedSelection = ['', '']
sbs_files: list[str] = []


class sbs_mark_sel(sublime_plugin.TextCommand):
    def run(self, edit):
        global sbs_markedSelection

        window = sublime.active_window()
        view = window.active_view()
        sel = view.sel()

        region = sel[0]
        selectionText = view.substr(region)

        sbs_markedSelection[0] = sbs_markedSelection[1]
        sbs_markedSelection[1] = selectionText


class sbs_compare_files(sublime_plugin.ApplicationCommand):
    def run(self, A=None, B=None):
        global sbs_files

        if A is None or B is None:
            print('Compare Error: file(s) not specified')
            return

        A = os.path.abspath(A)
        B = os.path.abspath(B)
        if not os.path.isfile(A) or not os.path.isfile(B):
            print('Compare Error: file(s) not found: %s, %s' % (A, B))
            return

        sbs_files = [A, B]
        print('Comparing "%s" and "%s"' % (A, B))

        window = sublime.active_window()
        window.run_command('sbs_compare')


def get_view_contents(view):
    return view.substr(sublime.Region(0, view.size()))


def get_drawtype():
    return (
        sublime.DRAW_OUTLINED
        if sbs_settings().get('outlines_only', False)
        else sublime.DRAW_NO_OUTLINE
    )


class sbs_compare(sublime_plugin.TextCommand):
    def is_enabled(
        self, with_active=False, group=-1, index=-1, compare_selections=False
    ):
        if compare_selections:
            if len(self.view.sel()) == 2:
                return all(map(bool, self.view.sel()))
            if all(map(bool, sbs_markedSelection)):
                return True
            if (
                sbs_markedSelection[1]
                and len(self.view.sel()) == 1
                and bool(self.view.sel()[0])
            ):
                return True
            return False
        return True

    def run(
        self, edit, with_active=False, group=-1, index=-1, compare_selections=False
    ):
        global sbs_markedSelection, sbs_files

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
                openTabs.append([viewName, view])

        def create_comparison(
            view1_contents,
            view2_contents,
            syntax,
            name1_override=False,
            name2_override=False,
        ):
            view1_syntax = syntax
            view2_syntax = syntax

            # make new window
            active_window.run_command('new_window')
            new_window = sublime.active_window()
            new_window.set_layout(
                {
                    "cols": [0.0, 0.5, 1.0],
                    "rows": [0.0, 1.0],
                    "cells": [[0, 0, 1, 1], [1, 0, 2, 1]],
                }
            )

            if sbs_settings().get('hide_sidebar', False):
                new_window.set_sidebar_visible(False)
            if sbs_settings().get('hide_menu', False):
                new_window.set_menu_visible(False)
            if sbs_settings().get('hide_minimap', False):
                new_window.set_minimap_visible(False)
            if sbs_settings().get('hide_status_bar', False):
                new_window.set_status_bar_visible(False)
            if sbs_settings().get('hide_tabs', False):
                new_window.set_tabs_visible(False)

            # view names
            view_prefix = sbs_settings().get('display_prefix', '')
            view2_name = name2_override

            view1_name = (
                name1_override or active_view.file_name() or active_view.name() or 'untitled'
            )

            name1base = os.path.basename(view1_name)
            name2base = os.path.basename(view2_name)
            if name1base == name2base:
                dirname1 = os.path.dirname(view1_name)
                dirname2 = os.path.dirname(view2_name)

                path_prefix = os.path.commonprefix([dirname1, dirname2])
                if path_prefix != '':
                    path_prefix = path_prefix.replace('\\', '/')
                    path_prefix = path_prefix.split('/')[
                        :-1
                    ]  # leave last directory in path
                    path_prefix = '/'.join(path_prefix) + '/'
                    plen = len(path_prefix)
                    dirname1 = dirname1[plen:]
                    dirname2 = dirname2[plen:]

                separator = ' — '
                view1_name = name1base + separator + dirname1
                view2_name = name2base + separator + dirname2

                if dirname1 == dirname2:
                    view1_name = name1base
                    view2_name = name2base
            else:
                view1_name = name1base
                view2_name = name2base

            view1_name += ' (active)'
            view2_name += ' (other)'

            # view 1
            view1 = new_window.new_file(syntax=view1_syntax)
            view1.set_name(view_prefix + view1_name)
            view1.set_scratch(True)
            view1.settings().set("is_sbs_compare", True)
            view1.settings().set('word_wrap', 'false')
            if sbs_settings().get('read_only', False):
                view1.set_read_only(True)

            # view 2
            view2 = new_window.new_file(syntax=view2_syntax)
            view2.set_name(view_prefix + view2_name)
            view2.set_scratch(True)
            view2.settings().set("is_sbs_compare", True)
            view2.settings().set('word_wrap', 'false')
            if sbs_settings().get('read_only', False):
                view2.set_read_only(True)

            # place views into their corresponding group
            new_window.set_view_index(view1, 0, 0)
            new_window.set_view_index(view2, 1, 0)

            compare_views(view1, view2, view1_contents, view2_contents)
            ViewScrollSyncer(new_window, [view1, view2])

            # focus first view
            new_window.focus_view(view1)

        def on_click(index):
            if index > -1:
                # get original views' data
                view1_contents = get_view_contents(active_view)
                view2_contents = get_view_contents(openTabs[index][1])

                syntax = active_view.settings().get('syntax')

                create_comparison(
                    view1_contents, view2_contents, syntax, False, openTabs[index][0]
                )

        def compare_from_views(view1, view2):
            if view1.is_loading() or view2.is_loading():
                sublime.set_timeout(lambda: compare_from_views(view1, view2), 10)
            else:
                view1_contents = get_view_contents(view1)
                view2_contents = get_view_contents(view2)
                syntax = view1.settings().get('syntax')

                view1.close()
                view2.close()

                create_comparison(view1_contents, view2_contents, syntax, file1, file2)

        if len(sbs_files) > 0:
            file1 = sbs_files[0]
            file2 = sbs_files[1]

            view1 = active_window.open_file(file1)
            view2 = active_window.open_file(file2)

            compare_from_views(view1, view2)
            del sbs_files[:]
        elif compare_selections is True:
            sel = active_view.sel()

            if len(sel) == 2:
                selA = active_view.substr(sel[0])
                selB = active_view.substr(sel[1])
            else:
                selA = sbs_markedSelection[0]
                selB = sbs_markedSelection[1]
                if not selA:
                    selA, selB = selB, active_view.substr(sel[0])
                sbs_markedSelection = ['', '']

            syntax = active_view.settings().get('syntax')
            create_comparison(selA, selB, syntax, 'selection A', 'selection B')
        elif len(openTabs) == 1:
            on_click(0)
        else:
            if with_active is True:
                active_group, active_group_index = active_window.get_view_index(
                    active_view
                )

                if group == -1 and index == -1:
                    group = 0 if active_group == 1 else 1
                    other_active_view = active_window.active_view_in_group(group)
                    index = active_window.get_view_index(other_active_view)[1]

                if index > active_group_index:
                    index -= 1

                if group > active_group:
                    index += len(active_window.views_in_group(active_group)) - 1
                elif group < active_group:
                    index += 1

                on_click(index)
            else:
                menu_items = []
                for tab in openTabs:
                    fileName = tab[0]
                    if os.path.basename(fileName) == fileName:
                        menu_items.append([os.path.basename(fileName), ''])
                    else:
                        menu_items.append([os.path.basename(fileName), fileName])
                sublime.set_timeout(
                    self.view.window().show_quick_panel(menu_items, on_click)
                )


def compare_views(
    view1: sublime.View,
    view2: sublime.View,
    view1_contents: str,
    view2_contents: str
):
    bufferA, bufferB, highlightA, highlightB, found_intraline_changes = \
        compute_diff(view1_contents, view2_contents)

    view1.run_command('sbs_replace_view_contents', {'text': bufferA})
    view1.sel().clear()
    view1.sel().add(sublime.Region(0))
    view1.show(0)

    view2.run_command('sbs_replace_view_contents', {'text': bufferB})
    view2.sel().clear()
    view2.sel().add(sublime.Region(0))
    view2.show(0)

    highlight_lines(view1, highlightA, 'A')
    highlight_lines(view2, highlightB, 'B')

    num_intra = len(found_intraline_changes)
    num_removals = len(highlightA) - num_intra
    num_insertions = len(highlightB) - num_intra
    total = num_intra + num_removals + num_insertions
    message = (
        f"{num_intra} intra-line modifications, "
        f"{num_removals} lines removed, "
        f"{num_insertions} lines added. "
        f"{total} line differences in total."
    )
    if sbs_settings().get('line_count_popup', False):
        sublime.message_dialog(message)
    elif window := view1.window():
        window.status_message(message)

    if sbs_settings().get('enable_intraline', True):
        task = partial(colorize_intraline, view1, view2, found_intraline_changes)
        threading.Thread(target=task).start()


def compute_diff(
    view1_contents: str, view2_contents: str
) -> tuple[str, str, list[int], list[int], list[tuple[int, str, str]]]:
    linesA = deque(view1_contents.splitlines(False))
    linesB = deque(view2_contents.splitlines(False))

    if sbs_settings().has('ignore_pattern'):
        ignore_pattern = sbs_settings().get('ignore_pattern')
        pattern = re.compile(ignore_pattern, re.MULTILINE)
        view1_contents = pattern.sub('', view1_contents)
        view2_contents = pattern.sub('', view2_contents)

    if sbs_settings().get('ignore_whitespace', False):
        view1_contents = re.sub(r'[ \t]', '', view1_contents)
        view2_contents = re.sub(r'[ \t]', '', view2_contents)

    if sbs_settings().get('ignore_case', False):
        view1_contents = view1_contents.lower()
        view2_contents = view2_contents.lower()

    diffLinesA = view1_contents.splitlines(False)
    diffLinesB = view2_contents.splitlines(False)

    bufferA: list[str] = []
    bufferB: list[str] = []

    highlightA: list[int] = []
    highlightB: list[int] = []

    # An "intraline" difference is always a '-' line, possibly followed by
    # '?' line, and immediately followed by a '+' line; the next line after
    # that '+' might be another '?' line as well, or not.
    # In short it is a sequence of one of: "-+", "-?+", "-?+?", "-+?". We
    # don't want to look forward up to four characters, so we look at it
    # from the perspective of a "+".  Before a "+" we must have seen a "-"
    # or a "-?".  That is what we encode in `open_intraline_block`.
    diff = difflib.ndiff(diffLinesA, diffLinesB, charjunk=None)
    found_intraline_changes: list[tuple[int, str, str]] = []
    open_intraline_block = False
    for prev_line, line, next_line in triplewise(chain([""], diff, [""])):
        code = line[:1]
        if code == " ":
            bufferA.append(linesA.popleft())
            bufferB.append(linesB.popleft())

        elif code == "-":
            bufferA.append(linesA.popleft())
            highlightA.append(len(bufferA) - 1)
            if next_line.startswith((" ", "-")):
                bufferB.append("")

        elif code == "+":
            bufferB.append(linesB.popleft())
            highlightB.append(len(bufferB) - 1)
            if open_intraline_block:
                if highlightB[-1] != highlightA[-1]:
                    print(f"assertion failed: {highlightB[-1]} != {highlightA[-1]}")
                found_intraline_changes.append((highlightB[-1], bufferA[-1], bufferB[-1]))
            else:
                bufferA.append("")

        elif code == "?":
            # There is a cheap intra line diff here, but since we filtered
            # the view contents, we cannot use it.
            ...

        open_intraline_block = code == "-" or (code == "?" and prev_line.startswith("-"))

    return "\n".join(bufferA), "\n".join(bufferB), highlightA, highlightB, found_intraline_changes


def highlight_lines(view, lines, col):
    # full line diffs
    regionList = []
    markers = []
    for lineNum in lines:
        lineStart = view.text_point(lineNum, 0)
        markers.append(lineStart)
        lineEnd = view.text_point(lineNum + 1, -1)
        region = sublime.Region(lineStart, lineEnd)
        regionList.append(region)

    colour = "diff.deleted.sbs-compare"
    if col == 'B':
        colour = "diff.inserted.sbs-compare"

    drawType = get_drawtype()
    view.add_regions('diff_highlighted-' + col, regionList, colour, '', drawType)
    view.settings().set('sbs_markers', markers)


def colorize_intraline(
    view1: sublime.View,
    view2: sublime.View,
    found_intraline_changes: list[tuple[int, str, str]]
):
    subHighlightA, subHighlightB = compute_intraline_differences(view1, view2, found_intraline_changes)
    sub_highlight_lines(view1, subHighlightA, 'A')
    sub_highlight_lines(view2, subHighlightB, 'B')


def compute_intraline_differences(
    view1: sublime.View,
    view2: sublime.View,
    found_intraline_changes: list[tuple[int, str, str]]
) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    intraline_emptyspace = sbs_settings().get('intraline_emptyspace', False)
    subHighlightA: list[tuple[int, int, int]] = []
    subHighlightB: list[tuple[int, int, int]] = []
    for line_num, left, right in found_intraline_changes:
        s = difflib.SequenceMatcher(None, left, right)
        for tag, i1, i2, j1, j2 in s.get_opcodes():
            if tag != 'equal':  # == replace
                if intraline_emptyspace:
                    if tag == 'insert':
                        i2 += j2 - j1
                    if tag == 'delete':
                        j2 += i2 - i1

                subHighlightA.append((line_num, i1, i2))
                subHighlightB.append((line_num, j1, j2))

    return subHighlightA, subHighlightB


def sub_highlight_lines(view, lines, col):
    regionList = [
        sublime.Region(view.text_point(line, a), view.text_point(line, b))
        for line, a, b in lines
    ]
    color = "diff.inserted.char.sbs-compare" if col == 'B' else "diff.deleted.char.sbs-compare"
    drawType = get_drawtype()
    view.add_regions('diff_intraline-' + col, regionList, color, '', drawType)


class ViewScrollSyncer(object):
    def __init__(self, window, viewList):
        self.window = window
        self.views = viewList
        self.timeout_focused = 10
        self.timeout_unfocused = 50

        self.run()

    def update_scroll(self, view1, view2, lastUpdated):
        if lastUpdated == 'A':
            view2.set_viewport_position(view1.viewport_position(), False)
        elif lastUpdated == 'B':
            view1.set_viewport_position(view2.viewport_position(), False)

    def run(self):
        if not self.window.is_valid():
            return

        if self.window.id() != sublime.active_window().id():
            sublime.set_timeout(self.run, self.timeout_unfocused)
            return

        view1 = self.views[0]
        view2 = self.views[1]

        if not view1.is_valid() or not view2.is_valid():
            return

        vecA = view1.viewport_position()
        vecB = view2.viewport_position()

        if vecA != vecB:
            lastVecA0 = view1.settings().get('viewsync_last_vec0', 1)
            lastVecA1 = view1.settings().get('viewsync_last_vec1', 1)

            lastVecB0 = view2.settings().get('viewsync_last_vec0', 1)
            lastVecB1 = view2.settings().get('viewsync_last_vec1', 1)

            lastVecA = (lastVecA0, lastVecA1)
            lastVecB = (lastVecB0, lastVecB1)

            lastUpdated = ''

            if lastVecA != vecA:
                lastUpdated = 'A'

                view1.settings().set('viewsync_last_vec0', vecA[0])
                view1.settings().set('viewsync_last_vec1', vecA[1])

                view2.settings().set('viewsync_last_vec0', vecA[0])
                view2.settings().set('viewsync_last_vec1', vecA[1])

            if lastVecB != vecB:
                lastUpdated = 'B'

                view1.settings().set('viewsync_last_vec0', vecB[0])
                view1.settings().set('viewsync_last_vec1', vecB[1])

                view2.settings().set('viewsync_last_vec0', vecB[0])
                view2.settings().set('viewsync_last_vec1', vecB[1])

            if lastUpdated != '':
                self.update_scroll(view1, view2, lastUpdated)

        sublime.set_timeout(self.run, self.timeout_focused)


def sbs_scroll_to(view, prev=False):
    if not view.settings().get('is_sbs_compare'):
        return

    current_pos = view.sel()[0].begin()
    regions = view.settings().get('sbs_markers')
    if prev:
        regions.reverse()

    for highlight in regions:
        found = False
        if prev:
            if highlight < current_pos:
                found = True
        else:
            if highlight > current_pos:
                found = True

        if found:
            view.sel().clear()
            view.sel().add(sublime.Region(highlight))
            view.show(highlight)
            return

    msg = 'Reached the ' + 'beginning' if prev else 'end'
    view.window().show_quick_panel([msg], None)


class sbs_prev_diff(sublime_plugin.TextCommand):
    def is_visible(self):
        return self.view.settings().get("is_sbs_compare", False)

    def run(self, edit, string=''):
        sbs_scroll_to(self.view, prev=True)


class sbs_next_diff(sublime_plugin.TextCommand):
    def is_visible(self):
        return self.view.settings().get("is_sbs_compare", False)

    def run(self, edit, string=''):
        sbs_scroll_to(self.view)


class sbs_select_text(sublime_plugin.TextCommand):
    def run(self, edit, index=''):
        window = self.view.window()

        if index == '':
            menu_items = ['Select removed text', 'Select added text']
            window.show_quick_panel(
                menu_items,
                lambda i: window.run_command('sbs_select_text', {'index': i}),
            )
            return

        view = window.views()[index]
        view.sel().clear()
        regions = (
            view.get_regions('diff_highlighted-A')
            + view.get_regions('diff_highlighted-B')
            + view.get_regions('diff_intraline-A')
            + view.get_regions('diff_intraline-B')
        )

        combined_regions = []
        # hacky but necessary to combine regions both start==end AND end==start
        # there's probably a better way to do this
        for it in range(0, 2):
            for r in regions:
                skip = False
                for cr in combined_regions:
                    if r.a == cr.b or r.b == cr.a:
                        cr.b = max(r.b, cr.b)
                        skip = True
                        break
                if not skip:
                    combined_regions.append(r)

        for r in combined_regions:
            view.sel().add(r)
