# fmt: off

"""Workspace controller for ASE-GUI workspace mode.

Coordinates file selection from explorer with appropriate viewers.
"""

from pathlib import Path

import ase.gui.ui_qt as ui
from ase.gui.file_classifier import FileClassifier, FileType
from ase.gui.images import Images
from ase.gui.text_viewer_qt import TextViewer


class WorkspaceController:
    """Controller for workspace mode operations."""
    
    def __init__(self, gui, root_directory):
        """Initialize workspace controller.
        
        Args:
            gui: GUI instance
            root_directory: Root directory path for workspace
        """
        self.gui = gui
        self.root_directory = Path(root_directory).resolve()
        self.text_viewers = {}  # Map of filepath -> TextViewer instance
        self.tab_filepaths = {}  # Map of tab_id -> filepath for tracking open files
        
    def handle_file_selection(self, filepath):
        """Handle file selection from explorer.
        
        Args:
            filepath: Path to selected file
        """
        filepath = Path(filepath)
        
        # Classify the file
        ftype = FileClassifier.classify(filepath)
        
        if ftype == FileType.STRUCTURE:
            self._open_structure_file(filepath)
        elif ftype == FileType.TRAJECTORY:
            self._open_trajectory_file(filepath)
        elif ftype == FileType.VOLUMETRIC:
            self._open_volumetric_file(filepath)
        elif ftype == FileType.TEXT_INPUT:
            self._open_text_file(filepath)
        else:
            # Try to open as structure file anyway
            try:
                self._open_structure_file(filepath)
            except Exception as e:
                ui.showinfo(
                    'Unknown File Type',
                    f'Cannot determine how to open: {filepath.name}\n\n'
                    f'Error: {e}'
                )
    
    def _open_structure_file(self, filepath):
        """Open a structure file in the atomic viewer.
        
        Args:
            filepath: Path to structure file
        """
        try:
            # Check if this file is already open in a tab
            filepath_str = str(filepath)
            for tab_id, file_path in self.tab_filepaths.items():
                if file_path == filepath_str:
                    # File already open, just switch to that tab
                    self.gui.switch_tab(tab_id)
                    try:
                        self.gui.window.canvas.setFocus()
                    except Exception:
                        pass
                    return
            
            # File not open yet, read it
            new_images = Images()
            new_images.read([str(filepath)], slice(None))
            
            # Add as a new tab instead of replacing current content
            self.gui.add_tab(filepath_str, new_images)
            
            # Track which file is in which tab
            self.tab_filepaths[self.gui.current_tab] = filepath_str
            
            # Update window title
            self.gui.window.win.setWindowTitle(f'ASE-GUI - {filepath.name}')
            
            # Set focus back to canvas so arrow keys work for atom manipulation
            try:
                self.gui.window.canvas.setFocus()
            except Exception:
                pass
            
        except Exception as e:
            ui.error('Error Opening Structure File',
                    f'Could not open {filepath.name}:\n{e}')
    
    def _open_trajectory_file(self, filepath):
        """Open a trajectory file in the trajectory player.
        
        Args:
            filepath: Path to trajectory file
        """
        try:
            # Check if this file is already open in a tab
            filepath_str = str(filepath)
            for tab_id, file_path in self.tab_filepaths.items():
                if file_path == filepath_str:
                    # File already open, just switch to that tab
                    self.gui.switch_tab(tab_id)
                    try:
                        self.gui.window.canvas.setFocus()
                    except Exception:
                        pass
                    return
            
            # File not open yet, read the trajectory
            new_images = Images()
            new_images.read([str(filepath)], slice(None))
            
            # Add as a new tab instead of replacing current content
            self.gui.add_tab(filepath_str, new_images)
            
            # Track which file is in which tab
            self.tab_filepaths[self.gui.current_tab] = filepath_str
            
            # Update window title
            self.gui.window.win.setWindowTitle(f'ASE-GUI - {filepath.name}')
            
            # Open movie player if multiple frames
            if len(self.gui.images) > 1:
                self.gui.movie()
            
            # Set focus back to canvas so arrow keys work for atom manipulation
            try:
                self.gui.window.canvas.setFocus()
            except Exception:
                pass
                
        except Exception as e:
            ui.error('Error Opening Trajectory File',
                    f'Could not open {filepath.name}:\n{e}')
    
    def _open_volumetric_file(self, filepath):
        """Open a volumetric data file.
        
        Args:
            filepath: Path to volumetric file
        """
        # Try to open with volumetric visualizer if available
        try:
            from ase.io import read
            
            # Check if this file is already open in a tab
            filepath_str = str(filepath)
            for tab_id, file_path in self.tab_filepaths.items():
                if file_path == filepath_str:
                    # File already open, just switch to that tab
                    self.gui.switch_tab(tab_id)
                    try:
                        self.gui.window.canvas.setFocus()
                    except Exception:
                        pass
                    return
            
            # Try to read the file - for CHGCAR/LOCPOT this will give the structure
            atoms = read(str(filepath))
            
            # Load structure into viewer as a new tab
            new_images = Images()
            new_images.initialize([atoms])
            
            self.gui.add_tab(filepath_str, new_images)
            
            # Track which file is in which tab
            self.tab_filepaths[self.gui.current_tab] = filepath_str
            
            # Update window title
            self.gui.window.win.setWindowTitle(f'ASE-GUI - {filepath.name}')
            
            # Set focus back to canvas so arrow keys work for atom manipulation
            try:
                self.gui.window.canvas.setFocus()
            except Exception:
                pass
            
            # Show info about volumetric data
            ui.showinfo(
                'Volumetric File Loaded',
                f'Loaded structure from {filepath.name}\n\n'
                'The atomic structure is displayed in the viewer.\n'
                'For full volumetric visualization, use external tools like VESTA.'
            )
            
        except Exception as e:
            # If can't read, show as text
            ui.showwarning(
                'Volumetric File',
                f'Cannot visualize volumetric data from {filepath.name}\n\n'
                'Opening as text file instead.\n\n'
                f'Original error: {e}'
            )
            self._open_text_file(filepath)
    
    def _open_text_file(self, filepath):
        """Open a text file in the text viewer.
        
        Args:
            filepath: Path to text file
        """
        try:
            filepath_str = str(filepath)
            
            # Check if already open
            if filepath_str in self.text_viewers:
                viewer = self.text_viewers[filepath_str]
                try:
                    viewer.show()
                    viewer.reload()
                    return
                except Exception:
                    # Window was closed, remove from dict
                    del self.text_viewers[filepath_str]
            
            # Create new viewer
            viewer = TextViewer(self.gui.window.win, title=f'Text Viewer - {filepath.name}')
            viewer.load_file(filepath)
            
            # Store reference
            self.text_viewers[filepath_str] = viewer
            
            # Clean up reference when window is closed
            def on_close():
                if filepath_str in self.text_viewers:
                    del self.text_viewers[filepath_str]
                viewer.close()
            
            viewer.window.protocol('WM_DELETE_WINDOW', on_close)
            
        except Exception as e:
            ui.error('Error Opening Text File',
                    f'Could not open {filepath.name}:\n{e}')
    
    def close_all_viewers(self):
        """Close all open text viewers."""
        for viewer in list(self.text_viewers.values()):
            try:
                viewer.close()
            except Exception:
                pass
        self.text_viewers.clear()
