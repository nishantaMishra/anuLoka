"""Qt version of AtomsEditor - table for editing atom properties."""

from dataclasses import dataclass
from typing import Callable

import numpy as np

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit
)
from PyQt5.QtCore import Qt

import ase.gui.ui_qt as ui
from ase.gui.i18n import _


@dataclass
class Column:
    name: str
    displayname: str
    widget_width: int
    getvalue: Callable
    setvalue: Callable
    format_value: Callable = lambda obj: str(obj)


class AtomsEditor:
    """Qt-based atoms editor using QTableWidget."""

    def __init__(self, gui):
        gui.obs.change_atoms.register(self.update_table_from_atoms)

        self.win = ui.Window(_('Edit atoms'))
        self.gui = gui
        self._updating = False  # Prevent recursion during updates

        # Create the table widget
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        
        # Connect signals
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.cellChanged.connect(self.cell_changed)

        # Set up columns
        def get_symbol(atoms, i):
            return atoms.symbols[i]

        def set_symbol(atoms, i, value):
            from ase.data import atomic_numbers
            if value not in atomic_numbers:
                return False
            atoms.symbols[i] = value
            return True

        class GetSetPos:
            def __init__(self, c):
                self.c = c

            def set_position(self, atoms, i, value):
                try:
                    value = float(value)
                except ValueError:
                    return False
                atoms.positions[i, self.c] = value
                return True

            def get_position(self, atoms, i):
                return atoms.positions[i, self.c]

        self.columns = []
        self.columns.append(Column('symbol', _('symbol'), 60, get_symbol, set_symbol))
        
        for c, axisname in enumerate('xyz'):
            column = Column(
                axisname,
                axisname,
                92,
                GetSetPos(c).get_position,
                GetSetPos(c).set_position,
                format_value=lambda val: f'{val:.4f}',
            )
            self.columns.append(column)

        # Configure table columns
        self.table.setColumnCount(len(self.columns) + 1)  # +1 for ID column
        headers = [_('id')] + [col.displayname for col in self.columns]
        self.table.setHorizontalHeaderLabels(headers)
        
        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID column
        for i, col in enumerate(self.columns):
            self.table.setColumnWidth(i + 1, col.widget_width)

        # Add table to window
        if hasattr(self.win, 'win') and hasattr(self.win.win, 'layout'):
            layout = self.win.win.layout()
            if layout is None:
                layout = QVBoxLayout(self.win.win)
            layout.addWidget(self.table)
        else:
            # Fallback: add directly to the window's central area
            try:
                self.win.win.setCentralWidget(self.table)
            except:
                pass

        self.update_table_from_atoms()

    @property
    def atoms(self):
        return self.gui.atoms

    def update_table_from_atoms(self):
        """Refresh the table from current atoms."""
        self._updating = True
        try:
            self.table.setRowCount(len(self.atoms))
            
            for i in range(len(self.atoms)):
                # ID column (read-only)
                id_item = QTableWidgetItem(str(i))
                id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 0, id_item)
                
                # Data columns
                for j, col in enumerate(self.columns):
                    value = col.format_value(col.getvalue(self.atoms, i))
                    item = QTableWidgetItem(value)
                    self.table.setItem(i, j + 1, item)

            # Update selection to match GUI selection
            mask = self.gui.images.selected[:len(self.atoms)]
            selection = np.arange(len(self.atoms))[mask]
            
            self.table.clearSelection()
            for idx in selection:
                self.table.selectRow(idx)
        finally:
            self._updating = False

    def selection_changed(self):
        """Handle table selection change."""
        if self._updating:
            return
        
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        indices = list(selected_rows)
        self.gui.set_selected_atoms(indices)

    def cell_changed(self, row, column):
        """Handle cell edit."""
        if self._updating:
            return
        
        if column == 0:  # ID column is not editable
            return
        
        col_idx = column - 1  # Adjust for ID column
        if col_idx < 0 or col_idx >= len(self.columns):
            return
        
        item = self.table.item(row, column)
        if item is None:
            return
        
        value = item.text()
        col = self.columns[col_idx]
        
        # Try to apply the change
        result = col.setvalue(self.atoms, row, value)
        
        # Update the display with formatted value
        self._updating = True
        try:
            formatted = col.format_value(col.getvalue(self.atoms, row))
            item.setText(formatted)
        finally:
            self._updating = False
        
        # Redraw
        self.gui.set_frame()
