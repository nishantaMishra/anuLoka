# AnuLok: the world of molecules

Basically, edited codes of ase gui. 

While development execute
```bash
python3 -m ase gui
```

Execute the command in the project directory to open the GUI.


Added features:
- Multiple tabs support
- Opens native file browser dialogs for loading and saving files.
- Presets for view configurations. I, J and K.
- Panning with keypress "P"  (Double right click to trigger panning.)
- Supports undo/redo of atom movements with Ctrl+Z / Ctrl+Y
- Tab location on hovering the tab bar.
- Support for XDATCAR.
- Axes gizmo: Alignment of structure by clicking the axes.
- Ctrl+W to close tab.
- PDOS toolbar button to plot PDOS.
- Opening directories in workspace mode.
- Drag and drop files to open them.


# Known Issues
1. `ase/ase_dragdrop_gui.py` has been moved into the `ase/` package.

# To do
- Better UI or DOS popup window. Selection of suborbitals is still kind of confusing. Now way to know if any suborbital is selected or not.
- Clicking tab should the option to close it.
