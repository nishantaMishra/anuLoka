# fmt: off

"""
UI Backend Selector for ASE-GUI.

This module determines whether to use Qt or Tkinter as the UI backend.
Set environment variable ASE_GUI_BACKEND=qt to use Qt, or ASE_GUI_BACKEND=tk for Tkinter.
Default is Qt if PyQt5 is available, otherwise falls back to Tkinter.
"""

import os
import sys

# Determine backend preference
_backend = os.environ.get('ASE_GUI_BACKEND', 'qt').lower()

# Try to use Qt backend first if requested
_use_qt = False
if _backend == 'qt':
    try:
        from PyQt5.QtWidgets import QApplication
        # Test if we can create an application
        if QApplication.instance() is None:
            _app = QApplication(sys.argv)
        _use_qt = True
        print("[ASE-GUI] Using Qt backend")
    except ImportError:
        print("[ASE-GUI] PyQt5 not available, falling back to Tkinter")
        _use_qt = False
    except Exception as e:
        print(f"[ASE-GUI] Qt initialization failed: {e}, falling back to Tkinter")
        _use_qt = False

if _use_qt:
    # Import everything from ui_qt
    from ase.gui.ui_qt import *
else:
    # Import everything from the original Tkinter-based ui module
    # We need to import the original ui.py renamed to ui_tk.py
    from ase.gui.ui_tk import *
