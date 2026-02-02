# fmt: off

"""Qt-based File explorer sidebar for ASE-GUI workspace mode.

Provides a Qt-based file tree view for browsing directories.
"""

import os
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QLabel, 
    QPushButton, QFrame, QHeaderView, QAbstractItemView
)
from PyQt5.QtCore import Qt, QDir, QModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon, QFont

from ase.gui.file_classifier import FileClassifier, FileType


class FileExplorer(QWidget):
    """File explorer sidebar widget using Qt QTreeView."""
    
    def __init__(self, parent, root_directory, callback=None):
        """Initialize file explorer.
        
        Args:
            parent: Parent Qt widget
            root_directory: Root directory path to display
            callback: Function to call when file is selected, receives filepath
        """
        super().__init__(parent)
        
        self.root_directory = Path(root_directory).resolve()
        self.callback = callback
        self.current_selection = None
        
        # Store mapping of items to paths
        self.item_to_path = {}
        
        # Set minimum size for the explorer
        self.setMinimumWidth(180)
        self.setMinimumHeight(200)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Add title bar
        title_frame = QFrame()
        title_frame.setStyleSheet("background-color: #e0e0e0;")
        title_frame.setFixedHeight(25)
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(5, 0, 5, 0)
        
        title_label = QLabel(f'Workspace: {self.root_directory.name}')
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        refresh_btn = QPushButton('↻')
        refresh_btn.setFixedWidth(25)
        refresh_btn.setFlat(True)
        refresh_btn.clicked.connect(self.refresh)
        title_layout.addWidget(refresh_btn)
        
        layout.addWidget(title_frame)
        
        # Create tree view
        self.tree = QTreeView()
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(15)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setSizePolicy(
            self.tree.sizePolicy().horizontalPolicy(),
            self.tree.sizePolicy().verticalPolicy()
        )
        
        # Create model
        self.model = QStandardItemModel()
        self.tree.setModel(self.model)
        
        # Connect signals
        self.tree.clicked.connect(self._on_select)
        self.tree.doubleClicked.connect(self._on_double_click)
        self.tree.expanded.connect(self._on_expand)
        
        layout.addWidget(self.tree, 1)  # stretch factor 1 so tree expands
        
        # Store reference to frame for compatibility
        self.frame = self
        self._packed = False
        self._parent_widget = parent
        
        # Populate tree
        self.refresh()
    
    def pack(self, **kwargs):
        """Pack the explorer frame (Qt compatibility - add to parent's layout)."""
        if self._packed:
            return
        # Use stored parent reference
        parent = self._parent_widget
        if parent is not None:
            layout = parent.layout()
            if layout is not None:
                layout.addWidget(self, 1)  # stretch factor 1
                self.show()
                self._packed = True
    
    def grid(self, **kwargs):
        """Grid the explorer frame (Qt compatibility - add to parent's layout)."""
        self.pack(**kwargs)
    
    def refresh(self):
        """Refresh the file tree."""
        self.model.clear()
        self.item_to_path.clear()
        
        # Create root item
        root_item = self.model.invisibleRootItem()
        
        # Check if directory exists
        if not self.root_directory.exists():
            print(f"FileExplorer: Directory does not exist: {self.root_directory}")
            return
        
        self._populate_tree(root_item, self.root_directory)
        print(f"FileExplorer: Populated {self.model.rowCount()} items from {self.root_directory}")
    
    def _get_icon_for_type(self, path):
        """Get display text with icon for file/directory."""
        if path.is_dir():
            return '📁 ' + path.name
        else:
            ftype = FileClassifier.classify(path)
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
            return f'{icon} {path.name}'
    
    def _populate_tree(self, parent_item, directory):
        """Recursively populate tree with directory contents.
        
        Args:
            parent_item: Parent QStandardItem
            directory: Path object of directory to populate
        """
        try:
            # Get all items in directory
            items = sorted(directory.iterdir(), 
                          key=lambda p: (not p.is_dir(), p.name.lower()))
            
            for item in items:
                # Skip hidden files
                if item.name.startswith('.'):
                    continue
                
                # Create tree item
                display_name = self._get_icon_for_type(item)
                tree_item = QStandardItem(display_name)
                tree_item.setEditable(False)
                
                # Store path mapping
                self.item_to_path[id(tree_item)] = item
                tree_item.setData(str(item), Qt.UserRole)
                
                parent_item.appendRow(tree_item)
                
                # If directory, add a dummy child so it shows as expandable
                if item.is_dir():
                    dummy = QStandardItem('Loading...')
                    dummy.setData('__dummy__', Qt.UserRole)
                    tree_item.appendRow(dummy)
                    
        except PermissionError:
            pass
        except Exception as e:
            print(f'Error populating tree: {e}')
    
    def _on_expand(self, index):
        """Handle tree expansion to lazily load subdirectories."""
        item = self.model.itemFromIndex(index)
        if item is None:
            return
        
        path_str = item.data(Qt.UserRole)
        if path_str and path_str != '__dummy__':
            path = Path(path_str)
            if path.is_dir():
                # Check if we have only a dummy child
                if item.rowCount() == 1:
                    child = item.child(0)
                    if child and child.data(Qt.UserRole) == '__dummy__':
                        # Remove dummy and populate
                        item.removeRow(0)
                        self._populate_tree(item, path)
    
    def _on_select(self, index):
        """Handle file/directory selection."""
        item = self.model.itemFromIndex(index)
        if item is None:
            return
        
        path_str = item.data(Qt.UserRole)
        if path_str and path_str != '__dummy__':
            path = Path(path_str)
            self.current_selection = path
            
            # Don't trigger callback for directory selection
            if path.is_file() and self.callback:
                self.callback(str(path))
    
    def _on_double_click(self, index):
        """Handle double-click to open files or expand directories."""
        item = self.model.itemFromIndex(index)
        if item is None:
            return
        
        path_str = item.data(Qt.UserRole)
        if path_str and path_str != '__dummy__':
            path = Path(path_str)
            if path.is_file() and self.callback:
                # Trigger callback on double-click for files
                self.callback(str(path))
            # Directories are handled automatically by tree expansion
    
    def get_selection(self):
        """Get currently selected path."""
        return self.current_selection
