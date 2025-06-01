Compare Side-By-Side
================

This package adds a simple side-by-side comparison tool to Sublime Text.
Here is us on [Package Control](https://packagecontrol.io/packages/Compare%20Side-By-Side) and
here on [GitHub](https://github.com/kaste/Compare-Side-By-Side/).

Features
---
  - Easily select two tabs or selections to compare
  - Comparison results open in a new window
  - Empty lines added so common code lines up
  - Count number of lines changed
  - Highlighting of changed lines
  - Intra-line diff highlighting
  - Synchronized scrolling

Installation Options
---
  - Search for and install using [Package Control](https://sublime.wbond.net/installation)
    (ctrl+shift+P, "Install Package")
  - Clone or extract this repo to a new folder in your Sublime 'Packages' folder  
    (*Preferences -> Browse Packages*)

Usage Options
---
  - Right click on a tab and select "Compare with..."
  - Right click somewhere in the active view and select "Compare with..."
  - Right click on a tab and select "Compare with active tab"
  - Highlight text, right click -> "Mark selection for comparison"
    Mark a second selection, then right click -> "Compare selections"
  - Create two selections by holding CTRL, then "Compare selections"
  - From the command line: [see README_COMMANDS.md](README_COMMANDS.md)
  - Jump around: `,` or `.`. But also: Jump to next: `alt+n`, jump to previous: `alt+p`
  
Configuration
---
  - The standard diff scopes/colors are used, these are
    `diff.inserted.sbs-compare`, `diff.inserted.char.sbs-compare`,
    `diff.deleted.sbs-compare`, `diff.deleted.char.sbs-compare`.
    Note that I just added the suffix ".sbs-compare" to them.
    You can change the colors in your color scheme (ctrl+shift+P,
    "UI: Customize Color Scheme").
  - Other options can be configured in SBSCompare.sublime-settings
    To access: *Preferences -> Package Settings -> Compare Side-By-Side*

License & Contributing
---
 - [MIT license](LICENSE)
 - Pull requests welcome!
 - Fork of https://bitbucket.org/dougty/sublime-compare-side-by-side/
