"""
Compatibility shim: the drag-and-drop launcher was moved to
`ase/ase_dragdrop_gui.py` inside the `ase` package.

Run it as a module:

  python -m ase.ase_dragdrop_gui

Or run the package-local script directly:

  python3 ase/ase_dragdrop_gui.py

This top-level file remains as a small shim to point users to the new
location.
"""

from __future__ import annotations

import sys

try:
    # Try to run the moved module in-package if requested
    from ase.ase_dragdrop_gui import main

    if __name__ == "__main__":
        main()
except Exception:
    # If importing/running fails (for example during packaging), print a helpful message
    print("The drag-and-drop launcher has been moved to 'ase/ase_dragdrop_gui.py'.")
    print("Run with: python -m ase.ase_dragdrop_gui")
    sys.exit(1)
