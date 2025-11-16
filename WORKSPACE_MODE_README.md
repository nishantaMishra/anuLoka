# ASE-GUI Workspace Mode

This document describes the new **workspace mode** feature for ASE-GUI that allows opening and browsing entire directories with a file explorer sidebar.

## Overview

ASE-GUI now supports a workspace mode that enables you to:
- Open a directory instead of individual files
- Browse files and subdirectories in a sidebar file explorer
- Open different file types with appropriate viewers:
  - **Structure files** (POSCAR, CONTCAR, CIF, etc.) → Atomic viewer
  - **Trajectory files** (XDATCAR, .traj, etc.) → Trajectory player  
  - **Volumetric files** (CHGCAR, LOCPOT) → Structure viewer with info
  - **Text input files** (INCAR, KPOINTS, etc.) → Built-in text viewer

The main 3D atomic viewer and all existing menu functionality remain unchanged.

## Usage

### Opening a Directory

To open ASE-GUI in workspace mode, simply provide a directory path:

```bash
python -m ase.gui /path/to/directory
```

For example, to browse a VASP calculation directory:

```bash
python -m ase.gui ~/calculations/my_vasp_run/
```

### File Explorer Sidebar

When in workspace mode, a file explorer sidebar appears on the left side of the window showing:
- 📁 Directories
- ⚛️ Structure files (POSCAR, CONTCAR, CIF, XYZ, etc.)
- 🎬 Trajectory files (XDATCAR, .traj, etc.)
- 📊 Volumetric data files (CHGCAR, LOCPOT, etc.)
- 📝 Text input files (INCAR, KPOINTS, OUTCAR, etc.)
- 📄 Other files

**Navigation:**
- **Click** on a file to select it
- **Double-click** on directories to expand/collapse them
- Use the **↻ Refresh** button to reload the file tree

### File Type Handling

#### Structure Files
Files like POSCAR, CONTCAR, CIF, XYZ, PDB, etc. are opened directly in the atomic viewer:
- The structure is loaded and displayed in the 3D viewer
- You can rotate, zoom, and manipulate as usual
- All menu options (View, Tools, Setup, etc.) work normally

#### Trajectory Files
Files like XDATCAR or .traj containing multiple frames:
- Opens in the atomic viewer with all frames loaded
- The Movie window opens automatically for playback
- Navigate through frames with the trajectory controls

#### Volumetric Files
Files like CHGCAR, LOCPOT, ELFCAR:
- The atomic structure is extracted and displayed
- An info dialog explains that full volumetric visualization requires external tools like VESTA
- The structure can still be viewed and manipulated normally

#### Text Input Files
Files like INCAR, KPOINTS, POTCAR, OUTCAR:
- Opens in a separate text viewer window
- Basic syntax highlighting for readability
- Read-only display
- **Reload** button to refresh content
- Multiple text viewers can be open simultaneously

## Architecture

The workspace mode implementation consists of several new modules:

### `ase/gui/file_classifier.py`
Classifies files by type based on:
- Filename patterns (POSCAR, CHGCAR, etc.)
- File extensions (.cif, .xyz, .traj, etc.)
- Content sniffing for ambiguous cases

### `ase/gui/file_explorer.py`
Tkinter-based file tree widget:
- TreeView-based hierarchical display
- Icon-coded file types
- Lazy loading of subdirectories
- Refresh capability

### `ase/gui/text_viewer.py`
Text file viewer window:
- ScrolledText widget with basic syntax highlighting
- Read-only display
- Reload functionality
- Separate window per file

### `ase/gui/workspace.py`
Workspace controller that:
- Coordinates file selection from explorer
- Dispatches files to appropriate viewers
- Manages text viewer lifecycle
- Handles errors gracefully

### Modified Files

**`ase/gui/gui.py`:**
- Added `workspace_dir` parameter to `__init__`
- Added `_initialize_workspace()` method
- Updated `exit()` to clean up workspace resources
- Maintains backward compatibility (workspace_dir=None → normal mode)

**`ase/gui/ui.py`:**
- Added `workspace_mode` parameter to `ASEGUIWindow`
- PanedWindow layout for sidebar when in workspace mode
- Original layout preserved for normal mode

**`ase/gui/ag.py`:**
- Detects when a directory is provided as argument
- Passes `workspace_dir` to GUI initialization
- Maintains backward compatibility with file arguments

## Examples

### VASP Calculation Directory

```bash
# Open a VASP calculation directory
python -m ase.gui ~/vasp_calculations/rutile_optimization/

# In the GUI:
# - Click POSCAR to view initial structure
# - Click CONTCAR to view optimized structure  
# - Click XDATCAR to see optimization trajectory
# - Click INCAR to review input parameters
# - Click OUTCAR to check calculation output
# - Click CHGCAR to load charge density (structure only)
```

### Materials Database

```bash
# Browse a collection of structures
python -m ase.gui ~/structures/database/

# Navigate through subdirectories and open any structure file
```

### Normal File Mode (Still Works)

```bash
# Open specific files as before - no sidebar
python -m ase.gui structure1.cif structure2.xyz

# Open with options
python -m ase.gui -r 2,2,1 --bonds POSCAR
```

## Key Features

✅ **Backward Compatible:** All existing functionality works unchanged when opening files  
✅ **Flexible:** Mix of structure, trajectory, volumetric, and text files  
✅ **Intuitive:** Visual file type indicators and smart file handling  
✅ **Non-Intrusive:** Sidebar is only shown in workspace mode  
✅ **Robust:** Graceful error handling and fallbacks

## Known Limitations

- Volumetric visualization shows structure only (use external tools like VESTA for 3D charge density)
- Very large directories may take time to populate
- Text viewer has basic syntax highlighting only
- Hidden files (starting with '.') are not shown in the explorer

## Future Enhancements

Potential improvements could include:
- Full volumetric data visualization integration
- File search/filter in explorer
- Configurable file type associations
- Multiple structure comparison side-by-side
- Integration with calculation workflow tools

## Technical Notes

- Uses tkinter's PanedWindow for resizable sidebar
- File explorer uses TreeView with lazy loading
- TextViewer uses ScrolledText widget
- File classification is extensible via FileClassifier class
- All new functionality is opt-in (only when directory provided)

## Troubleshooting

**Q: Sidebar doesn't appear**  
A: Make sure you're providing a directory path, not a file path

**Q: File icons are all generic**  
A: Unicode emojis may not render on all systems; functionality is unaffected

**Q: Text viewer shows garbled text**  
A: Binary files opened as text will show raw bytes; this is expected

**Q: Cannot see hidden files**  
A: By design, files starting with '.' are filtered out

## Getting Started

To try workspace mode immediately:

```bash
# Navigate to a directory with structure files
cd /path/to/your/structures/

# Launch ASE-GUI in workspace mode
python -m ase.gui .
```

The file explorer will appear on the left, and you can start clicking files to open them!
