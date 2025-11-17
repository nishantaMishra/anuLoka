# Aṇu Loka: the world of molecules

A GUI for visualizing and manipulating atomic structures using the Atomic Simulation Environment (ASE) library.


## Installation
```bash
git clone https://github.com/nishantaMishra/anuLoka.git
cd anuLoka
```

## Execution
```bash
python3 -m ase gui 
python3 -m ase -T gui /path/to/your/directory/or/file.  
```


# Added features:
- Multiple tabs support
- Opens native file browser dialogs for loading and saving files.
- Presets for view configurations. I, J and K.
- Panning with keypress "P"  (Double right click to trigger panning.)
- Supports undo/redo of atom movements with Ctrl+Z / Ctrl+Y
- Tab location on hovering the tab bar.
- Support for XDATCAR.
- Axes gizmo: Alignment of structure by clicking the axes.
- Ctrl+W to close tab.
- DOS toolbar button to plot DOS. (expects native vaspkit installation)
- Opening directories in workspace mode.
- Drag and drop files to open them.


# To do
- Better UI or DOS popup window. Selection of suborbitals is still kind of confusing. Now way to know if any suborbital is selected or not.
- Clicking tab should the option to close it. 
- Band structure plots.
