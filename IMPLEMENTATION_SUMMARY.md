# ASE-GUI Workspace Mode - Implementation Summary

## Overview
This implementation adds a workspace mode to ASE-GUI that enables opening directories with a file explorer sidebar. Files are routed to appropriate viewers based on type while preserving all existing functionality.

## New Files Created

### 1. `ase/gui/file_classifier.py`
**Purpose:** Classify files by type for intelligent routing

**Key Components:**
- `FileType` enum: STRUCTURE, TRAJECTORY, VOLUMETRIC, TEXT_INPUT, UNKNOWN
- `FileClassifier` class with classification logic:
  - Matches against known filenames (POSCAR, CHGCAR, etc.)
  - Checks file extensions (.cif, .xyz, .traj, etc.)
  - Optional content sniffing for ambiguous cases
  - Helper methods: `is_structure_file()`, `is_volumetric_file()`, etc.

**Supported File Types:**
- **Structure:** POSCAR, CONTCAR, CIF, XYZ, PDB, MOL, SDF, GEN, etc.
- **Volumetric:** CHGCAR, LOCPOT, CHG, ELFCAR, AECCAR*, etc.
- **Trajectory:** XDATCAR, .traj, .nc, .dcd, .xtc, .trr
- **Text Input:** INCAR, KPOINTS, POTCAR, OUTCAR, DOSCAR, etc.

### 2. `ase/gui/file_explorer.py`
**Purpose:** File browser sidebar widget

**Key Components:**
- `FileExplorer` class using tkinter TreeView
- Features:
  - Hierarchical directory display with icons
  - Lazy loading of subdirectories on expand
  - Single-selection file navigation
  - Refresh button to reload tree
  - Double-click to expand/collapse folders
  - Filters hidden files (starting with '.')
  
**File Icons:**
- 📁 Directories
- ⚛️ Structure files
- 🎬 Trajectory files
- 📊 Volumetric files
- 📝 Text input files
- 📄 Generic files

### 3. `ase/gui/text_viewer.py`
**Purpose:** Display text files in a viewer window

**Key Components:**
- `TextViewer` class with ScrolledText widget
- Features:
  - Read-only text display
  - Basic syntax highlighting:
    - Comments (lines starting with # or !)
    - Section headers (all caps or contains =)
    - Numbers
  - Reload button to refresh content
  - Separate window per file
  - Auto-cleanup on close

### 4. `ase/gui/workspace.py`
**Purpose:** Coordinate workspace operations

**Key Components:**
- `WorkspaceController` class
- `handle_file_selection()` - main dispatch method:
  - STRUCTURE → `_open_structure_file()` → atomic viewer
  - TRAJECTORY → `_open_trajectory_file()` → trajectory player
  - VOLUMETRIC → `_open_volumetric_file()` → structure + info dialog
  - TEXT_INPUT → `_open_text_file()` → text viewer
  - UNKNOWN → attempt structure load or show error
  
**Features:**
- Manages multiple text viewer windows
- Graceful error handling with user dialogs
- Integrates with existing GUI Images system
- Clean shutdown via `close_all_viewers()`

## Modified Files

### 1. `ase/gui/ui.py`
**Changes to `ASEGUIWindow.__init__()`:**

**Added Parameters:**
- `workspace_mode=False` - enables workspace layout

**Layout Changes:**
```python
if workspace_mode:
    # Create PanedWindow with sidebar and canvas
    self.paned_window = tk.PanedWindow(orient=HORIZONTAL)
    self.sidebar_frame = tk.Frame()  # For file explorer
    canvas_frame = tk.Frame()
    self.canvas = tk.Canvas(canvas_frame, ...)
else:
    # Original layout
    self.canvas = tk.Canvas(self.win, ...)
```

**New Attributes:**
- `self.workspace_mode` - flag
- `self.sidebar_frame` - container for file explorer
- `self.paned_window` - resizable split container

**Backward Compatibility:**
- Normal mode (workspace_mode=False) uses original layout
- All existing functionality unchanged

### 2. `ase/gui/gui.py`
**Changes to `GUI.__init__()`:**

**Added Parameters:**
- `workspace_dir=None` - directory path for workspace mode

**New Attributes:**
```python
self.workspace_mode = workspace_dir is not None
self.workspace_dir = workspace_dir
self.workspace_controller = None
self.file_explorer = None
```

**Initialization Flow:**
```python
# Pass workspace_mode to ASEGUIWindow
self.window = ui.ASEGUIWindow(..., workspace_mode=self.workspace_mode)

# Initialize workspace if directory provided
if self.workspace_mode:
    self._initialize_workspace()
```

**New Methods:**

**`_initialize_workspace()`:**
```python
def _initialize_workspace(self):
    # Create workspace controller
    self.workspace_controller = WorkspaceController(self, self.workspace_dir)
    
    # Create file explorer in sidebar
    self.file_explorer = FileExplorer(
        self.window.sidebar_frame,
        self.workspace_dir,
        callback=self.workspace_controller.handle_file_selection
    )
    
    # Update window title
    self.window.win.title(f'ASE-GUI - Workspace: {workspace_name}')
```

**Updated Methods:**

**`exit()`:**
```python
def exit(self, event=None):
    # Clean up workspace resources
    if self.workspace_mode and self.workspace_controller:
        self.workspace_controller.close_all_viewers()
    
    # Original cleanup
    for process in self.subprocesses:
        process.terminate()
    self.window.close()
```

**Backward Compatibility:**
- `workspace_dir=None` → normal single-file mode
- All existing parameters and behavior preserved

### 3. `ase/gui/ag.py`
**Changes to `CLICommand.run()`:**

**Directory Detection:**
```python
workspace_dir = None
if len(args.filenames) == 1:
    path = Path(args.filenames[0])
    if path.is_dir():
        workspace_dir = str(path.resolve())
        # Initialize with empty atoms for workspace mode
        images = Images()
        images.initialize([Atoms()])
```

**GUI Creation:**
```python
gui = GUI(images, args.rotations, args.bonds, args.graph, 
         workspace_dir=workspace_dir)
```

**Backward Compatibility:**
- Multiple files → normal mode
- Single file → normal mode
- Single directory → workspace mode
- No arguments → empty GUI (normal mode)

## Integration Points

### File Selection → Viewer Routing
```
User clicks file in explorer
    ↓
FileExplorer callback
    ↓
WorkspaceController.handle_file_selection()
    ↓
FileClassifier.classify()
    ↓
Type-specific handler (_open_structure_file, etc.)
    ↓
Appropriate viewer (atomic, trajectory, text)
```

### Structure File Loading
```
_open_structure_file()
    ↓
Images.read() (ASE's existing system)
    ↓
gui.images.initialize()
    ↓
gui.set_frame()
    ↓
Atomic viewer displays structure
```

### Text File Loading
```
_open_text_file()
    ↓
TextViewer instance created
    ↓
viewer.load_file()
    ↓
Separate window opens with content
    ↓
Reference stored in workspace_controller.text_viewers
```

## Error Handling

All file operations include try-except blocks with user-friendly dialogs:

```python
try:
    # Operation
except Exception as e:
    ui.error('Error Title', f'Could not open {filename}:\n{e}')
```

Special cases:
- **Volumetric files:** If can't extract structure → open as text with warning
- **Unknown files:** Try structure load → show info dialog on failure
- **Text viewer already open:** Reload existing window instead of creating new

## Testing Recommendations

### Unit Tests
- FileClassifier: Test classification of all file types
- FileExplorer: Test tree population and selection
- WorkspaceController: Test file routing logic

### Integration Tests
- Open directory with mixed file types
- Open structure files from explorer
- Open text files (INCAR, KPOINTS)
- Open trajectory files (XDATCAR)
- Open volumetric files (CHGCAR)
- Test backward compatibility (opening files directly)

### Manual Testing Scenarios
1. **VASP calculation directory:**
   - Open POSCAR, CONTCAR, XDATCAR
   - View INCAR, KPOINTS, OUTCAR
   - Check CHGCAR handling

2. **Materials database:**
   - Navigate subdirectories
   - Open various structure formats (CIF, XYZ, PDB)

3. **Backward compatibility:**
   - `ase gui file.xyz` (no sidebar)
   - `ase gui *.cif` (no sidebar)
   - `ase gui -r 2,2,1 POSCAR` (no sidebar)

4. **Edge cases:**
   - Empty directory
   - Directory with no readable files
   - Large directory (>1000 files)
   - Permission-restricted directories

## Dependencies

**New Python stdlib imports:**
- `pathlib.Path` - file path handling
- `tkinter.scrolledtext` - text viewer
- `tkinter.ttk.Treeview` - file explorer

**Existing ASE dependencies:**
- `ase.gui.ui` - UI components
- `ase.gui.images` - image handling
- `ase.io` - file reading

No new external dependencies required.

## Performance Considerations

- **File classification:** Fast (~microseconds per file)
- **Tree population:** Lazy loading prevents slowdown on large directories
- **Text loading:** Only small files (<100KB) are content-sniffed
- **Structure loading:** Uses existing ASE I/O (unchanged performance)

## Extensibility

### Adding New File Types

**1. Update FileClassifier:**
```python
NEW_TYPE_FILES = {'NEWFILE', 'OTHERFILE'}
NEW_TYPE_EXTENSIONS = {'.new', '.nw'}
```

**2. Add handler in WorkspaceController:**
```python
def _open_new_type_file(self, filepath):
    # Custom handling
    pass
```

**3. Update dispatch in handle_file_selection:**
```python
elif ftype == FileType.NEW_TYPE:
    self._open_new_type_file(filepath)
```

### Custom File Viewers

Create viewer class similar to `TextViewer`:
```python
class CustomViewer:
    def __init__(self, parent, title):
        self.window = tk.Toplevel(parent)
        # Setup UI
    
    def load_file(self, filepath):
        # Load and display
        pass
```

## Documentation

**User Documentation:**
- `WORKSPACE_MODE_README.md` - comprehensive user guide

**Code Documentation:**
- All new classes have docstrings
- All methods have docstrings
- Inline comments for complex logic

## Future Enhancements

Potential additions (not implemented):
1. **Search/filter in file explorer**
2. **Full volumetric visualization** (3D charge density)
3. **Side-by-side structure comparison**
4. **File watcher** (auto-reload on changes)
5. **Custom file associations** (user-configurable)
6. **Bookmarks/favorites** in explorer
7. **Recent files list**
8. **Export current structure from workspace**

## Conclusion

This implementation adds powerful directory browsing capabilities to ASE-GUI while maintaining complete backward compatibility. The modular design allows for easy extension and customization. All existing features remain unchanged when not in workspace mode.
