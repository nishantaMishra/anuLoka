# fmt: off

"""File explorer sidebar for ASE-GUI workspace mode.

Provides a tkinter-based file tree view for browsing directories.
"""

import os
import tkinter as tk
import tkinter.ttk as ttk
from pathlib import Path

from ase.gui.file_classifier import FileClassifier, FileType


class FileExplorer:
    """File explorer sidebar widget using tkinter Treeview."""
    
    def __init__(self, parent, root_directory, callback=None):
        """Initialize file explorer.
        
        Args:
            parent: Parent tkinter widget
            root_directory: Root directory path to display
            callback: Function to call when file is selected, receives filepath
        """
        self.root_directory = Path(root_directory).resolve()
        self.callback = callback
        self.current_selection = None
        
        # Create main frame for explorer
        self.frame = tk.Frame(parent)
        
        # Add title label
        title_frame = tk.Frame(self.frame, bg='#e0e0e0', height=25)
        title_frame.pack(side=tk.TOP, fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text=f'Workspace: {self.root_directory.name}',
            bg='#e0e0e0',
            anchor=tk.W,
            padx=5
        )
        title_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create refresh button
        refresh_btn = tk.Button(
            title_frame,
            text='↻',
            command=self.refresh,
            bg='#e0e0e0',
            relief=tk.FLAT,
            padx=5
        )
        refresh_btn.pack(side=tk.RIGHT)
        
        # Create scrollbar and treeview
        tree_frame = tk.Frame(self.frame)
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree = ttk.Treeview(
            tree_frame,
            yscrollcommand=scrollbar.set,
            selectmode='browse',
            takefocus=0  # Prevent TreeView from taking keyboard focus
        )
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.tree.yview)
        
        # Hide the first column (tree structure column)
        self.tree.heading('#0', text='Files', anchor=tk.W)
        
        # Bind selection event
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Double-1>', self._on_double_click)
        
        # Prevent arrow keys from being captured by TreeView
        # Let them propagate to the main GUI for atom manipulation
        def block_arrow_keys(event):
            # Return 'break' to stop event propagation for arrow keys
            return 'break'
        
        # Block arrow key navigation in the tree
        for key in ('<Up>', '<Down>', '<Left>', '<Right>',
                    '<KP_Up>', '<KP_Down>', '<KP_Left>', '<KP_Right>'):
            self.tree.bind(key, block_arrow_keys)
        
        # Store mapping of tree item IDs to paths
        self.item_to_path = {}
        self.path_to_item = {}
        
        # Populate tree
        self.refresh()
    
    def pack(self, **kwargs):
        """Pack the explorer frame."""
        self.frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        """Grid the explorer frame."""
        self.frame.grid(**kwargs)
    
    def refresh(self):
        """Refresh the file tree."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.item_to_path.clear()
        self.path_to_item.clear()
        
        # Populate root
        self._populate_tree('', self.root_directory)
        
    def _populate_tree(self, parent_item, directory):
        """Recursively populate tree with directory contents.
        
        Args:
            parent_item: Parent tree item ID (empty string for root)
            directory: Path object of directory to populate
        """
        try:
            # Get all items in directory
            items = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            
            for item in items:
                # Skip hidden files
                if item.name.startswith('.'):
                    continue
                    
                # Determine icon based on type
                if item.is_dir():
                    icon = '📁'
                    display_name = f'{icon} {item.name}'
                else:
                    ftype = FileClassifier.classify(item)
                    if ftype == FileType.STRUCTURE:
                        icon = '⚛️'
                    elif ftype == FileType.TRAJECTORY:
                        icon = '🎬'
                    elif ftype == FileType.VOLUMETRIC:
                        icon = '📊'
                    elif ftype == FileType.TEXT_INPUT:
                        icon = '📝'
                    else:
                        icon = '📄'
                    display_name = f'{icon} {item.name}'
                
                # Insert item into tree
                item_id = self.tree.insert(
                    parent_item,
                    'end',
                    text=display_name,
                    open=False
                )
                
                # Store mappings
                self.item_to_path[item_id] = item
                self.path_to_item[str(item)] = item_id
                
                # If directory, add a dummy child so it shows as expandable
                if item.is_dir():
                    self.tree.insert(item_id, 'end', text='Loading...')
                    
        except PermissionError:
            pass
        except Exception as e:
            print(f'Error populating tree: {e}')
    
    def _on_expand(self, event):
        """Handle tree expansion to lazily load subdirectories."""
        item_id = self.tree.focus()
        if item_id in self.item_to_path:
            path = self.item_to_path[item_id]
            if path.is_dir():
                # Remove dummy children
                children = self.tree.get_children(item_id)
                for child in children:
                    self.tree.delete(child)
                # Populate real children
                self._populate_tree(item_id, path)
    
    def _on_select(self, event):
        """Handle file/directory selection."""
        selected = self.tree.selection()
        if not selected:
            return
            
        item_id = selected[0]
        if item_id in self.item_to_path:
            path = self.item_to_path[item_id]
            self.current_selection = path
            
            # Don't trigger callback for directory selection
            if path.is_file() and self.callback:
                self.callback(str(path))
    
    def _on_double_click(self, event):
        """Handle double-click to expand/collapse directories."""
        # Get the item under the mouse
        item_id = self.tree.identify('item', event.x, event.y)
        if not item_id:
            return
            
        if item_id in self.item_to_path:
            path = self.item_to_path[item_id]
            if path.is_dir():
                # Toggle expansion
                if self.tree.item(item_id, 'open'):
                    self.tree.item(item_id, open=False)
                else:
                    # Expand and load children if not already loaded
                    children = self.tree.get_children(item_id)
                    if len(children) == 1 and self.tree.item(children[0], 'text') == 'Loading...':
                        # Remove dummy and populate
                        self.tree.delete(children[0])
                        self._populate_tree(item_id, path)
                    self.tree.item(item_id, open=True)
    
    def get_selection(self):
        """Get currently selected path."""
        return self.current_selection
