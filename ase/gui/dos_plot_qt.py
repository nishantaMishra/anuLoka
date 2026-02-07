# fmt: off

"""Qt version of DOS plotting dialog for ASE-GUI with checkbox interface."""

import os
import sys
import shutil
import subprocess
import textwrap
from functools import partial
from pathlib import Path

from PyQt5.QtWidgets import QMenu, QWidget
from PyQt5.QtCore import Qt

import ase.gui.ui_qt as ui
from ase.gui.i18n import _


class CompactRows(ui.Rows):
    """Rows container that packs items tightly to the top."""
    def create(self, parent):
        widget = super().create(parent)
        # Add stretch at the end to push items to the top
        if self._layout:
            self._layout.addStretch()
        return widget


class OrbitalContextMenu:
    """Context menu for selecting individual orbital components (p or d)."""
    
    def __init__(self, element, orbital_type, element_checks, sync_callback):
        """
        Args:
            element: Element name
            orbital_type: 'p' or 'd'
            element_checks: Reference to element_checks dict
            sync_callback: Function to call when orbital selection changes
        """
        self.element = element
        self.orbital_type = orbital_type
        self.element_checks = element_checks
        self.sync_callback = sync_callback
        
        if orbital_type == 'p':
            self.individual_orbitals = ['py', 'pz', 'px']
        elif orbital_type == 'd':
            self.individual_orbitals = ['dxy', 'dyz', 'dz2', 'dxz', 'dx2']
        else:
            self.individual_orbitals = []
    
    def toggle_individual(self, orbital):
        """Toggle an individual orbital checkbox."""
        if orbital in self.element_checks[self.element]['individual_orbitals']:
            self.element_checks[self.element]['individual_orbitals'][orbital].var.set(
                not self.element_checks[self.element]['individual_orbitals'][orbital].var.get()
            )
            self.sync_callback(self.element, self.orbital_type)
    
    def select_all(self):
        """Select all individual orbitals of this type."""
        for orb in self.individual_orbitals:
            if orb in self.element_checks[self.element]['individual_orbitals']:
                self.element_checks[self.element]['individual_orbitals'][orb].var.set(True)
        self.sync_callback(self.element, self.orbital_type)
    
    def clear_all(self):
        """Clear all individual orbitals of this type."""
        for orb in self.individual_orbitals:
            if orb in self.element_checks[self.element]['individual_orbitals']:
                self.element_checks[self.element]['individual_orbitals'][orb].var.set(False)
        self.sync_callback(self.element, self.orbital_type)


class DOSPlotter:
    """Dialog for plotting DOS using the ase.DOS module with checkbox interface."""
    
    def __init__(self, gui):
        self.gui = gui
        self.win = ui.Window(_('Plot DOS'))
        
        # Override closeEvent to log all window closures
        original_close_event = self.win.win.closeEvent
        def logged_close_event(event):
            import traceback
            print("\n" + "="*60)
            print("Qt closeEvent triggered (X button, Escape, or system close)")
            print("Stack trace:")
            traceback.print_stack()
            print("="*60 + "\n")
            if original_close_event:
                original_close_event(event)
        self.win.win.closeEvent = logged_close_event
        
        # Initialize checkbox states early
        self.element_checks = {}
        self.orbital_checks = {}
        self.tdos_check = None
        self.fill = False
        self.grid = False
        
        # For real-time preview
        self.auto_refresh_enabled = False
        self.plot_figure = None
        self.plot_axes = None
        self._update_pending = False
        self._text_debounce_timer = None
        
        # Get current file directory as default location
        self.default_location = self._get_default_location()
        
        # Import DOS module and read files
        self.pdos_files = None
        self.tdos_data = None
        self.available_elements = []
        self.color_schemes = []
        
        # Try to load DOS module and read files
        self._load_dos_module()
        self._read_dos_files()
        
        # Directory selection
        self.win.add(_('DOS Data Directory:'))
        self.location = ui.Entry(self.default_location, width=35)
        self.win.add([self.location, ui.Button(_('Browse...'), self.browse_directory)])
        
        if self.pdos_files:
            self._build_selection_interface()
        else:
            self.win.add(ui.Label(_('No DOS files found in directory.\n'
                                   'Required: vaspout.h5 OR (INCAR, DOSCAR, PROCAR files)\n'
                                   'Files will be generated automatically if possible.')))
        
        self._add_options_and_customization()
        
        # Auto-refresh checkbox
        self.auto_refresh_check = ui.CheckButton(_('Live preview'), False, self._toggle_auto_refresh)
        
        # Buttons - at the very end
        self.win.add([self.auto_refresh_check,
                     ui.Button(_('Plot'), self.plot),
                     ui.Button(_('Refresh'), self.refresh),
                     ui.Button(_('Close'), self.close)])
        
        print("DOSPlotter.__init__() completed successfully")
    
    def __del__(self):
        """Destructor - called when object is garbage collected."""
        print("\n" + "="*60)
        print("DOSPlotter.__del__() called - object being destroyed")
        print("="*60 + "\n")
    
    def _get_default_location(self):
        """Get default directory for DOS files."""
        # First priority: Use workspace directory if in workspace mode
        if hasattr(self.gui, 'workspace_dir') and self.gui.workspace_dir:
            return self.gui.workspace_dir
        
        # Second priority: Try to use the directory of the currently loaded file
        if hasattr(self.gui, 'images') and hasattr(self.gui.images, 'filenames'):
            current_file = self.gui.images.filenames[self.gui.frame]
            if current_file:
                # Remove @index notation if present
                if '@' in current_file:
                    current_file = current_file.split('@')[0]
                file_dir = os.path.dirname(os.path.abspath(current_file))
                return file_dir
        
        # Fall back to current working directory
        return os.getcwd()
    
    def _load_dos_module(self):
        """Import DOS plotting module."""
        try:
            dos_module_path = Path(__file__).parent.parent / 'DOS'
            if str(dos_module_path) not in sys.path:
                sys.path.insert(0, str(dos_module_path))
            
            from PDOS import (
                read_pdos_files, 
                read_pdos_from_hdf5,
                try_generate_pdos_dat_files,
                plot_pdos
            )
            
            self.read_pdos_files = read_pdos_files
            self.read_pdos_from_hdf5 = read_pdos_from_hdf5
            self.try_generate_pdos_dat_files = try_generate_pdos_dat_files
            self.plot_pdos = plot_pdos
            
            # Try to import h5py for HDF5 support
            try:
                import h5py
                self.HAS_H5PY = True
            except ImportError:
                self.HAS_H5PY = False
            
            # Import color manager
            try:
                from color_manager import get_available_schemes
                self.color_schemes = get_available_schemes()
            except ImportError:
                self.color_schemes = ['vesta', 'jmol', 'user', 'cpk', 'mp']
                
        except ImportError as e:
            ui.showerror(_('Error'), 
                        _('Could not import DOS module.\n'
                          'Make sure ase/DOS/PDOS.py is available.\n\n'
                          f'Error: {e}'))
            self.read_pdos_files = None
    
    def _read_dos_files(self):
        """Read PDOS files from the default location."""
        if not self.read_pdos_files:
            return
        
        location = self.default_location
        
        # First, try to read from vaspout.h5
        if self.HAS_H5PY:
            try:
                self.pdos_files, self.tdos_data = self.read_pdos_from_hdf5(location)
                if self.pdos_files:
                    pass
            except Exception as e:
                pass
        
        # Fall back to .dat files if HDF5 reading failed
        if not self.pdos_files:
            self.pdos_files = self.read_pdos_files(location)
            if not self.pdos_files:
                # Try to generate PDOS files
                try:
                    generated = self.try_generate_pdos_dat_files(location)
                    if generated:
                        self.pdos_files = self.read_pdos_files(location)
                except Exception as e:
                    pass
        
        if self.pdos_files:
            self.available_elements = sorted(self.pdos_files.keys())
    
    def _build_selection_interface(self):
        """Build the checkbox interface for element and orbital selection."""
        from PyQt5.QtWidgets import QGroupBox, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget, QFrame
        
        # Add TDOS option with auto-refresh callback
        self.tdos_check = ui.CheckButton(_('TDOS (Total DOS)'))
        self.win.add(self.tdos_check)
        
        # Create a horizontal layout for PDOS and Markers side by side
        self.win.add(_(''))  # Small spacer
        
        # Available orbitals
        all_orbitals = ['s', 'p', 'd']
        p_individual = ['py', 'pz', 'px']
        d_individual = ['dxy', 'dyz', 'dz2', 'dxz', 'dx2']
        
        # Store context menu bindings to apply later
        self.context_menu_bindings = []
        
        # Store all checkboxes/widgets for connecting auto-refresh
        self._auto_refresh_widgets = []
        
        # --- PDOS and Markers Side-by-Side ---
        pdos_rows = []
        pdos_label = ui.Label(_('Partial DOS:'))
        hint_label = ui.Label(_('(Right-click p/d for orbitals)'))
        pdos_rows.append([pdos_label, hint_label])
        
        # Create element rows compactly
        for element in self.available_elements:
            elem_check = ui.CheckButton(element)
            self.element_checks[element] = {
                'check': elem_check,
                'orbitals': {},
                'individual_orbitals': {}
            }
            
            # Create individual orbital checkboxes (hidden but functional)
            for p_orb in p_individual:
                p_check = ui.CheckButton(p_orb)
                self.element_checks[element]['individual_orbitals'][p_orb] = p_check
            
            for d_orb in d_individual:
                d_check = ui.CheckButton(d_orb)
                self.element_checks[element]['individual_orbitals'][d_orb] = d_check
            
            # Orbital checkboxes for this element
            orbital_checks = []
            for orbital in all_orbitals:
                orb_check = ui.CheckButton(orbital)
                self.element_checks[element]['orbitals'][orbital] = orb_check
                orbital_checks.append(orb_check)
                
                # Store binding info for later (after widgets are created)
                if orbital in ['p', 'd']:
                    self.context_menu_bindings.append((element, orbital, orb_check))
            
            # Build compact row: [element checkbox] [s] [p] [d]
            row_widgets = [elem_check] + orbital_checks
            pdos_rows.append(row_widgets)

        pdos_col = CompactRows(pdos_rows)
        
        # --- Vertical Markers Section (Right Column) ---
        markers_rows = []
        markers_rows.append([ui.Label(' ')])  # Spacer
        markers_rows.append([ui.Label(_('Vertical Markers:'))])
        
        self.fermi_marker_check = ui.CheckButton(_('Fermi level (E=0)'), True)
        markers_rows.append([self.fermi_marker_check])
        
        self.dband_marker_check = ui.CheckButton(_('d-band center'))
        markers_rows.append([self.dband_marker_check])
        
        # Empty label for check button since "Custom" is already in the entry
        self.custom_marker_check = ui.CheckButton('')
        self.custom_marker_label_entry = ui.Entry('Custom', width=12)
        self.custom_marker_value_entry = ui.SpinBox(0.0, -100, 100, 0.5, width=4)
        markers_rows.append([self.custom_marker_check, self.custom_marker_label_entry, 
                      self.custom_marker_value_entry, ui.Label(_('eV'))])
        
        # --- Options under Vertical Markers ---
        markers_rows.append([ui.Label(' ')])
        markers_rows.append([ui.Label(_('Options:'))])

        # Spin filter
        self.spin_var = ui.RadioButtons(['Both', 'Up', 'Down'], 
                                        ['both', 'up', 'down'], 
                                        self._on_setting_changed)
        self.spin_var.value = 'both'
        markers_rows.append([ui.Label(_('Spin:')), self.spin_var])

        # Cutoff
        self.cutoff_entry = ui.SpinBox(0.0, 0.0, 10000.0, 0.1, width=6)
        markers_rows.append([ui.Label(_('DOS Cutoff:')), self.cutoff_entry])
        
        markers_col = CompactRows(markers_rows)

        # Add columns side-by-side
        self.win.add([pdos_col, markers_col])
        
        # Attach context menus after window is shown
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, self._attach_all_context_menus)
        
        # --- Color Scheme Section ---
        self.win.add(_('Color Scheme:'))
        color_options = self.color_schemes
        self.color_scheme_var = ui.RadioButtons(
            [c.upper() for c in color_options],
            color_options,
            self._on_setting_changed
        )
        self.color_scheme_var.value = 'vesta' if 'vesta' in self.color_schemes else (self.color_schemes[0] if self.color_schemes else None)
        self.win.add(self.color_scheme_var)
        
        # Connect auto-refresh handlers after widgets are created
        QTimer.singleShot(150, self._connect_auto_refresh_handlers)
    
    def _attach_all_context_menus(self):
        """Attach all context menus after widgets are created."""
        for element, orbital_type, checkbox_widget in self.context_menu_bindings:
            self._attach_context_menu(element, orbital_type, checkbox_widget)
    
    def _attach_context_menu(self, element, orbital_type, checkbox_widget):
        """Attach a right-click context menu to a p or d checkbox."""
        try:
            # For Qt, the CheckButton stores the QCheckBox as .widget
            qt_widget = None
            if hasattr(checkbox_widget, 'widget') and checkbox_widget.widget is not None:
                qt_widget = checkbox_widget.widget
            
            if qt_widget is None:
                return
            
            # For Qt widgets, set context menu policy for right-click
            qt_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            qt_widget.customContextMenuRequested.connect(
                lambda pos, e=element, ot=orbital_type, w=qt_widget: self._show_orbital_menu_at_widget(e, ot, w)
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _show_orbital_menu_at_widget(self, element, orbital_type, widget):
        """Show context menu at the widget's position."""
        try:
            menu = QMenu()
            
            if orbital_type == 'p':
                individual_orbs = ['py', 'pz', 'px']
                menu_label = 'p-orbital components'
            else:
                individual_orbs = ['dxy', 'dyz', 'dz2', 'dxz', 'dx2']
                menu_label = 'd-orbital components'
            
            # Add label (disabled entry to act as header)
            header_action = menu.addAction(f"— {menu_label} —")
            header_action.setEnabled(False)
            menu.addSeparator()
            
            # Add checkable actions for each individual orbital
            for orb in individual_orbs:
                if orb in self.element_checks[element]['individual_orbitals']:
                    check = self.element_checks[element]['individual_orbitals'][orb]
                    action = menu.addAction(orb)
                    action.setCheckable(True)
                    action.setChecked(check.var.get() if hasattr(check.var, 'get') else False)
                    action.triggered.connect(
                        lambda checked, e=element, ot=orbital_type, o=orb: 
                            self._toggle_individual_orbital(e, ot, o, checked)
                    )
            
            menu.addSeparator()
            select_all_action = menu.addAction('Select all')
            select_all_action.triggered.connect(
                lambda: self._select_all_individual(element, orbital_type)
            )
            clear_all_action = menu.addAction('Clear all')
            clear_all_action.triggered.connect(
                lambda: self._clear_all_individual(element, orbital_type)
            )
            
            # Display menu at widget position
            from PyQt5.QtGui import QCursor
            menu.exec_(QCursor.pos())
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _toggle_individual_orbital(self, element, orbital_type, orbital, checked):
        """Toggle an individual orbital and sync with parent checkbox."""
        if orbital in self.element_checks[element]['individual_orbitals']:
            check = self.element_checks[element]['individual_orbitals'][orbital]
            if hasattr(check.var, 'set'):
                check.var.set(checked)
        self._on_individual_orbital_changed(element, orbital_type)
    
    def _on_individual_orbital_changed(self, element, orbital_type):
        """Handle individual orbital selection change and sync parent checkbox."""
        if orbital_type == 'p':
            individual_orbs = ['py', 'pz', 'px']
        else:
            individual_orbs = ['dxy', 'dyz', 'dz2', 'dxz', 'dx2']
        
        # Check if any are selected
        any_selected = any(
            self.element_checks[element]['individual_orbitals'][orb].var.get()
            for orb in individual_orbs
            if orb in self.element_checks[element]['individual_orbitals']
        )
        
        all_selected = all(
            self.element_checks[element]['individual_orbitals'][orb].var.get()
            for orb in individual_orbs
            if orb in self.element_checks[element]['individual_orbitals']
        )
        
        # Sync parent checkbox
        parent_check = self.element_checks[element]['orbitals'][orbital_type]
        if all_selected:
            parent_check.var.set(True)
        elif not any_selected:
            parent_check.var.set(False)
        # If mixed state, leave parent as is
    
    def _on_parent_orbital_changed(self, element, orbital_type):
        """Handle parent (p or d) checkbox change and sync individual orbitals."""
        if orbital_type == 'p':
            individual_orbs = ['py', 'pz', 'px']
        else:
            individual_orbs = ['dxy', 'dyz', 'dz2', 'dxz', 'dx2']
        
        parent_state = self.element_checks[element]['orbitals'][orbital_type].var.get()
        
        # Set all individual orbitals to match parent state
        for orb in individual_orbs:
            if orb in self.element_checks[element]['individual_orbitals']:
                self.element_checks[element]['individual_orbitals'][orb].var.set(parent_state)
    
    def _select_all_individual(self, element, orbital_type):
        """Select all individual orbitals of given type."""
        if orbital_type == 'p':
            individual_orbs = ['py', 'pz', 'px']
        else:
            individual_orbs = ['dxy', 'dyz', 'dz2', 'dxz', 'dx2']
        
        for orb in individual_orbs:
            if orb in self.element_checks[element]['individual_orbitals']:
                self.element_checks[element]['individual_orbitals'][orb].var.set(True)
        
        # Sync parent checkbox
        self.element_checks[element]['orbitals'][orbital_type].var.set(True)
    
    def _clear_all_individual(self, element, orbital_type):
        """Clear all individual orbitals of given type."""
        if orbital_type == 'p':
            individual_orbs = ['py', 'pz', 'px']
        else:
            individual_orbs = ['dxy', 'dyz', 'dz2', 'dxz', 'dx2']
        
        for orb in individual_orbs:
            if orb in self.element_checks[element]['individual_orbitals']:
                self.element_checks[element]['individual_orbitals'][orb].var.set(False)
        
        # Sync parent checkbox
        self.element_checks[element]['orbitals'][orbital_type].var.set(False)
    
    def _add_options_and_customization(self):
        """Add options and plot customization sections."""
        # Plot customization section
        self.win.add(_('\nPlot Customization:'))
        
        # Title with checkbox and font size
        default_title = ''
        if self.default_location:
            last_dirs = os.path.normpath(self.default_location).split(os.sep)[-4:]
            default_title = os.path.join(*last_dirs)
        
        # Create spinboxes with unique instances to avoid any potential sharing
        # These are created separately first to ensure each has its own state
        self.title_fontsize = ui.SpinBox(14, 8, 30, 1, width=4)
        self.xlabel_fontsize = ui.SpinBox(12, 8, 24, 1, width=3)
        self.ylabel_fontsize = ui.SpinBox(12, 8, 24, 1, width=3)
        
        # Create spinboxes for xlim and ylim
        self.xlim_min = ui.SpinBox(-20, -100, 100, 1, width=4)
        self.xlim_max = ui.SpinBox(20, -100, 100, 1, width=4)
        self.ylim_min = ui.SpinBox(0, -100, 1000, 1, width=4)
        self.ylim_max = ui.SpinBox(100, -100, 1000, 1, width=4)
        
        # Store initial values separately to avoid any mixing
        title_fs_initial = '14'
        xlabel_fs_initial = '12'
        ylabel_fs_initial = '12'
        
        # Title row
        self.show_title_check = ui.CheckButton(_('Title:'), True, None)
        self.title_entry = ui.Entry(default_title, width=34)
        self.win.add([self.show_title_check, self.title_entry, self.title_fontsize])
        
        # X-axis row
        self.show_xlabel_check = ui.CheckButton(_('X-axis:'), True, None)
        self.xlabel_entry = ui.Entry('Energy (eV)', width=17)
        xlim_label = ui.Label('  xlim:')
        self.win.add([self.show_xlabel_check, self.xlabel_entry, self.xlabel_fontsize, xlim_label, self.xlim_min, self.xlim_max])
        
        # Y-axis row
        self.show_ylabel_check = ui.CheckButton(_('Y-axis:'), True, None)
        self.ylabel_entry = ui.Entry('Density of States', width=17)
        ylim_label = ui.Label('  ylim:')
        self.win.add([self.show_ylabel_check, self.ylabel_entry, self.ylabel_fontsize, ylim_label, self.ylim_min, self.ylim_max])
        
        # Fill and Grid options
        self.fill_check = ui.CheckButton(_('Fill under curves'), False, None)
        self.grid_check = ui.CheckButton(_('Show grid'), False, None)
        self.win.add([self.fill_check, self.grid_check])
        
        self.win.add(_(''))  # Empty line separator
        
        # Attach tooltips to font size spinboxes after widgets are created
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, self._attach_fontsize_tooltips)
    
    def _attach_fontsize_tooltips(self):
        """Attach tooltips to font size spinboxes after widgets are created."""
        try:
            # Set tooltips using Qt's native setToolTip method
            if hasattr(self, 'title_fontsize') and hasattr(self.title_fontsize, 'widget'):
                self.title_fontsize.widget.setToolTip('Font size')
            
            if hasattr(self, 'xlabel_fontsize') and hasattr(self.xlabel_fontsize, 'widget'):
                self.xlabel_fontsize.widget.setToolTip('Font size')
            
            if hasattr(self, 'ylabel_fontsize') and hasattr(self.ylabel_fontsize, 'widget'):
                self.ylabel_fontsize.widget.setToolTip('Font size')
            
            if hasattr(self, 'xlim_min') and hasattr(self.xlim_min, 'widget'):
                self.xlim_min.widget.setToolTip('X-axis minimum')
            
            if hasattr(self, 'xlim_max') and hasattr(self.xlim_max, 'widget'):
                self.xlim_max.widget.setToolTip('X-axis maximum')
            
            if hasattr(self, 'ylim_min') and hasattr(self.ylim_min, 'widget'):
                self.ylim_min.widget.setToolTip('Y-axis minimum')
            
            if hasattr(self, 'ylim_max') and hasattr(self.ylim_max, 'widget'):
                self.ylim_max.widget.setToolTip('Y-axis maximum')
        except Exception:
            pass
        except Exception as e:
            pass
    
    def _toggle_auto_refresh(self, enabled=None):
        """Toggle auto-refresh mode."""
        if enabled is None:
            enabled = self.auto_refresh_check.var.get() if hasattr(self, 'auto_refresh_check') else False
        self.auto_refresh_enabled = enabled
        if enabled:
            # Trigger an initial plot
            self._schedule_auto_plot()
    
    def _connect_auto_refresh_handlers(self):
        """Connect change handlers to all widgets for auto-refresh."""
        try:
            from PyQt5.QtWidgets import QCheckBox, QRadioButton, QSpinBox, QDoubleSpinBox
            
            # Helper to connect a checkbox
            def connect_checkbox(check_widget):
                if hasattr(check_widget, 'widget') and check_widget.widget:
                    check_widget.widget.stateChanged.connect(self._on_setting_changed)
            
            # Helper to connect a spinbox
            def connect_spinbox(spin_widget):
                if hasattr(spin_widget, 'widget') and spin_widget.widget:
                    spin_widget.widget.valueChanged.connect(self._on_setting_changed)
            
            # Connect TDOS checkbox
            if self.tdos_check:
                connect_checkbox(self.tdos_check)
            
            # Connect element and orbital checkboxes
            for element, data in self.element_checks.items():
                connect_checkbox(data['check'])
                for orb_check in data['orbitals'].values():
                    connect_checkbox(orb_check)
                for ind_check in data['individual_orbitals'].values():
                    connect_checkbox(ind_check)
            
            # Connect marker checkboxes
            if hasattr(self, 'fermi_marker_check'):
                connect_checkbox(self.fermi_marker_check)
            if hasattr(self, 'dband_marker_check'):
                connect_checkbox(self.dband_marker_check)
            if hasattr(self, 'custom_marker_check'):
                connect_checkbox(self.custom_marker_check)
            
            # Connect fill and grid checkboxes
            if hasattr(self, 'fill_check'):
                connect_checkbox(self.fill_check)
            if hasattr(self, 'grid_check'):
                connect_checkbox(self.grid_check)
            
            # Connect axis limit spinboxes
            if hasattr(self, 'xlim_min'):
                connect_spinbox(self.xlim_min)
            if hasattr(self, 'xlim_max'):
                connect_spinbox(self.xlim_max)
            if hasattr(self, 'ylim_min'):
                connect_spinbox(self.ylim_min)
            if hasattr(self, 'ylim_max'):
                connect_spinbox(self.ylim_max)
            
            # Connect font size spinboxes
            if hasattr(self, 'title_fontsize'):
                connect_spinbox(self.title_fontsize)
            if hasattr(self, 'xlabel_fontsize'):
                connect_spinbox(self.xlabel_fontsize)
            if hasattr(self, 'ylabel_fontsize'):
                connect_spinbox(self.ylabel_fontsize)
            
            # Connect custom marker value spinbox
            if hasattr(self, 'custom_marker_value_entry'):
                connect_spinbox(self.custom_marker_value_entry)
            
            # Helper to connect text entry fields (use textEdited for debounced text changes)
            def connect_entry(entry_widget):
                if hasattr(entry_widget, 'widget') and entry_widget.widget:
                    entry_widget.widget.textEdited.connect(self._on_text_changed)
            
            # Connect text entry fields (title, xlabel, ylabel, custom marker label)
            if hasattr(self, 'title_entry'):
                connect_entry(self.title_entry)
            if hasattr(self, 'xlabel_entry'):
                connect_entry(self.xlabel_entry)
            if hasattr(self, 'ylabel_entry'):
                connect_entry(self.ylabel_entry)
            if hasattr(self, 'custom_marker_label_entry'):
                connect_entry(self.custom_marker_label_entry)
            if hasattr(self, 'cutoff_entry'):
                connect_spinbox(self.cutoff_entry)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _on_setting_changed(self, *args):
        """Called when any plot setting changes."""
        if self.auto_refresh_enabled:
            self._schedule_auto_plot()
    
    def _on_text_changed(self, *args):
        """Called when text entry changes; debounce with timer to avoid rapid updates."""
        if not self.auto_refresh_enabled:
            return
        # Debounce: restart timer on each keystroke
        from PyQt5.QtCore import QTimer
        if self._text_debounce_timer is None:
            self._text_debounce_timer = QTimer()
            self._text_debounce_timer.setSingleShot(True)
            self._text_debounce_timer.timeout.connect(self._on_setting_changed)
        self._text_debounce_timer.stop()
        self._text_debounce_timer.start(250)  # 250ms delay after last keystroke
    
    def _schedule_auto_plot(self):
        """Schedule an auto-plot with debouncing to avoid too frequent updates."""
        if self._update_pending:
            return
        
        self._update_pending = True
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(200, self._do_auto_plot)
    
    def _do_auto_plot(self):
        """Execute the auto-plot."""
        self._update_pending = False
        if not self.auto_refresh_enabled:
            return
        
        try:
            self._plot_internal(auto_refresh=True)
        except Exception as e:
            # Log errors during auto-refresh for debugging, but don't show error dialogs
            import traceback
            print(f"Auto-refresh error: {e}")
            traceback.print_exc()
            # Don't close the window or show error dialogs during auto-refresh
    
    def _show_tooltip(self, event, text):
        """Show tooltip on hover."""
        try:
            from PyQt5.QtWidgets import QToolTip
            from PyQt5.QtGui import QCursor
            QToolTip.showText(QCursor.pos(), text)
        except:
            pass
    
    def _hide_tooltip(self):
        """Hide tooltip."""
        try:
            from PyQt5.QtWidgets import QToolTip
            QToolTip.hideText()
        except:
            pass
    
    def browse_directory(self):
        """Open a native directory browser where possible."""
        from PyQt5.QtWidgets import QFileDialog
        
        initial_dir = self.location.value.strip() or self.default_location or os.getcwd()
        if not os.path.isdir(initial_dir):
            initial_dir = os.path.expanduser('~')

        directory = QFileDialog.getExistingDirectory(
            None,
            _('Select DOS Data Directory'),
            initial_dir
        )

        if directory:
            self.location.value = directory

    def _open_native_directory_dialog(self, initial_dir):
        """Try platform-specific native dialogs (Qt handles this automatically)."""
        return None

    def _browse_directory_windows(self, initial_dir):
        """Use Windows FolderBrowserDialog via PowerShell."""
        if not shutil.which('powershell'):
            return None

        env = os.environ.copy()
        env['ASE_DOS_INITIAL_DIR'] = initial_dir
        description = _('Select DOS Data Directory').replace("'", "''")
        script = textwrap.dedent(f"""
            $ErrorActionPreference='SilentlyContinue'
            Add-Type -AssemblyName System.Windows.Forms | Out-Null
            $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
            $dialog.Description = '{description}'
            $initial = $env:ASE_DOS_INITIAL_DIR
            if ($initial -and (Test-Path $initial)) {{
                $dialog.SelectedPath = $initial
            }}
            $dialog.ShowNewFolderButton = $true
            $result = $dialog.ShowDialog()
            if ($result -eq [System.Windows.Forms.DialogResult]::OK) {{
                Write-Output $dialog.SelectedPath
            }}
        """)

        completed = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
            capture_output=True,
            text=True,
            env=env
        )

        if completed.returncode == 0:
            path = completed.stdout.strip()
            if path:
                return path
        return None

    def _browse_directory_macos(self, initial_dir):
        """Use macOS choose folder dialog via AppleScript."""
        if not shutil.which('osascript'):
            return None

        env = os.environ.copy()
        env['ASE_DOS_INITIAL_DIR'] = initial_dir
        env['ASE_DOS_PROMPT'] = _('Select DOS Data Directory')
        script = textwrap.dedent("""
            set initialPath to POSIX file (system attribute "ASE_DOS_INITIAL_DIR")
            set promptText to system attribute "ASE_DOS_PROMPT"
            try
                set chosenFolder to choose folder with prompt promptText default location initialPath
                POSIX path of chosenFolder
            on error
                return ""
            end try
        """)

        completed = subprocess.run(
            ['osascript', '-'],
            input=script,
            capture_output=True,
            text=True,
            env=env
        )

        if completed.returncode == 0:
            path = completed.stdout.strip()
            if path:
                return path
        return None

    def _browse_directory_linux(self, initial_dir):
        """Try common Linux desktop file chooser commands."""
        commands = []
        filename = initial_dir if initial_dir.endswith(os.sep) else initial_dir + os.sep
        if shutil.which('zenity'):
            commands.append([
                'zenity', '--file-selection', '--directory',
                f"--title={_('Select DOS Data Directory')}",
                f"--filename={filename}"
            ])
        if shutil.which('kdialog'):
            commands.append([
                'kdialog', '--getexistingdirectory', initial_dir,
                '--title', _('Select DOS Data Directory')
            ])
        if shutil.which('qarma'):
            commands.append([
                'qarma', '--file-selection', '--directory',
                f"--title={_('Select DOS Data Directory')}",
                f"--filename={filename}"
            ])

        for cmd in commands:
            try:
                completed = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True
                )
                if completed.returncode == 0:
                    path = completed.stdout.strip()
                    if path:
                        return path
            except Exception as exc:
                pass

        return None
    
    def refresh(self):
        """Refresh DOS files from the selected directory."""
        location = self.location.value.strip()
        if not os.path.isdir(location):
            ui.showerror(_('Error'), _('Directory does not exist.'))
            return
        
        # Confirm before closing the current window
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            None,
            _('Confirm Refresh'),
            _('Refreshing will close this window and reopen with new data. Continue?'),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.default_location = location
        self.pdos_files = None
        self.available_elements = []
        
        # Re-read DOS files
        self._read_dos_files()
        
        # Close and reopen window with new data
        self.win.close()
        DOSPlotter(self.gui)
    
    def plot(self):
        """Execute DOS plotting (manual trigger)."""
        self._plot_internal(auto_refresh=False)
    
    def _plot_internal(self, auto_refresh=False):
        """Internal plotting method used by both manual and auto-refresh.
        
        Args:
            auto_refresh: If True, suppress error dialogs and just return on error
        """
        # Preserve focus to prevent input interruption during auto-refresh
        from PyQt5.QtWidgets import QApplication
        focused_widget = None
        if auto_refresh:
            try:
                focused_widget = QApplication.focusWidget()
            except Exception:
                pass
        
        if not self.pdos_files:
            if not auto_refresh:
                ui.showerror(_('Error'), _('No DOS files available.'))
            return
        
        # Build plotting_info from checkbox selections
        plotting_info = {}
        
        # Check if TDOS is selected
        # For TDOS, use empty list to signal total DOS plotting
        if self.tdos_check and self.tdos_check.var.get():
            plotting_info['tot'] = []
        
        # Check element selections
        for element, data in self.element_checks.items():
            if data['check'].var.get():
                # Get selected orbitals for this element
                selected_orbitals = []
                
                # First, add selected combined orbitals
                for orbital, orb_check in data['orbitals'].items():
                    if orb_check.var.get():
                        selected_orbitals.append(orbital)
                
                # Then, add selected individual orbitals
                for ind_orbital, ind_check in data['individual_orbitals'].items():
                    if ind_check.var.get():
                        selected_orbitals.append(ind_orbital)
                
                if selected_orbitals:
                    plotting_info[element] = selected_orbitals
        
        if not plotting_info:
            if not auto_refresh:
                ui.showerror(_('Error'), 
                            _('Please select at least one element/orbital or TDOS.'))
            return
        
        # Get spin filter
        spin_filter = None
        spin_value = self.spin_var.value
        if spin_value == 'up':
            spin_filter = 'UP'
        elif spin_value == 'down':
            spin_filter = 'DOWN'
        
        # Get fill and grid options
        fill = self.fill_check.var.get()
        show_grid = self.grid_check.var.get()
        
        # Get vertical marker options
        show_fermi = self.fermi_marker_check.var.get()
        show_dband = self.dband_marker_check.var.get()
        
        # Get custom marker value and label
        custom_marker = None
        custom_marker_label = None
        if self.custom_marker_check.var.get():
            custom_marker_str = self.custom_marker_value_entry.value
            custom_marker_label = self.custom_marker_label_entry.value.strip()
            if custom_marker_str is not None:
                try:
                    custom_marker = float(custom_marker_str)
                except (ValueError, TypeError):
                    if not auto_refresh:
                        ui.showerror(_('Error'), _('Invalid custom marker value.'))
                    return
            if not custom_marker_label:
                custom_marker_label = f'Custom ({custom_marker:.2f} eV)'
        
        # Get cutoff
        cutoff = self.cutoff_entry.value
        # Treat 0 (or close to 0) as disabled/no cutoff
        if cutoff < 1e-6:
            cutoff = None

        
        # Get color scheme
        color_scheme = self.color_scheme_var.value
        if color_scheme == '':
            color_scheme = None
        
        # Apply color scheme
        fill_colors = {}
        if color_scheme:
            try:
                dos_module_path = Path(__file__).parent.parent / 'DOS'
                if str(dos_module_path) not in sys.path:
                    sys.path.insert(0, str(dos_module_path))
                from color_manager import apply_color_scheme
                
                elements_for_scheme = list(plotting_info.keys())
                fill_colors = apply_color_scheme(elements_for_scheme, 
                                                 plotting_info, 
                                                 color_scheme)
            except Exception as e:
                print(f"Warning: Could not apply color scheme: {e}")
        
        # Get plot customization values
        # Check if user wants to show title/labels via checkboxes
        title = self.title_entry.value.strip() if self.show_title_check.var.get() else None
        xlabel = self.xlabel_entry.value.strip() if self.show_xlabel_check.var.get() else None
        ylabel = self.ylabel_entry.value.strip() if self.show_ylabel_check.var.get() else None
        title_fontsize = self.title_fontsize.value
        xlabel_fontsize = self.xlabel_fontsize.value
        ylabel_fontsize = self.ylabel_fontsize.value
        
        # Get xlim and ylim from spinboxes
        xlim_min_val = self.xlim_min.value
        xlim_max_val = self.xlim_max.value
        ylim_min_val = self.ylim_min.value
        ylim_max_val = self.ylim_max.value
        
        # Only apply xlim if values are different from defaults or if max > min
        xlim = None
        if xlim_min_val < xlim_max_val:
            xlim = (xlim_min_val, xlim_max_val)
        elif xlim_min_val >= xlim_max_val:
            if not auto_refresh:
                ui.showerror(_('Error'), _('xlim: minimum must be less than maximum'))
            return
        
        # Only apply ylim if values are different from defaults or if max > min
        ylim = None
        if ylim_min_val < ylim_max_val:
            ylim = (ylim_min_val, ylim_max_val)
        elif ylim_min_val >= ylim_max_val:
            if not auto_refresh:
                ui.showerror(_('Error'), _('ylim: minimum must be less than maximum'))
            return
        
        location = self.location.value.strip()
        
        # For auto-refresh, try to reuse existing figure
        fig = None
        if auto_refresh and self.plot_figure is not None:
            import matplotlib.pyplot as plt
            # Check if figure still exists
            if plt.fignum_exists(self.plot_figure.number):
                fig = self.plot_figure
                fig.clear()
        
        # Plot
        try:
            result = self.plot_pdos(self.pdos_files, plotting_info, title, 
                          spin_filter=spin_filter, fill=fill, location=location, 
                          fill_colors=fill_colors, cutoff=cutoff, show_grid=show_grid, 
                          xlabel=xlabel, ylabel=ylabel, 
                          title_fontsize=title_fontsize, 
                          xlabel_fontsize=xlabel_fontsize, 
                          ylabel_fontsize=ylabel_fontsize,
                          xlim=xlim, ylim=ylim,
                          show_fermi=show_fermi, show_dband=show_dband, 
                          custom_marker=custom_marker, custom_marker_label=custom_marker_label,
                          fig=fig, auto_refresh=auto_refresh)
            
            # Store reference to the figure for auto-refresh
            if result is not None:
                self.plot_figure = result
            else:
                # If plot_pdos doesn't return the figure, try to get current figure
                import matplotlib.pyplot as plt
                self.plot_figure = plt.gcf()
            
            # Restore focus after plot update to prevent input interruption
            if auto_refresh and focused_widget is not None:
                try:
                    if focused_widget.isVisible():
                        focused_widget.setFocus(Qt.OtherFocusReason)
                except Exception:
                    pass
                
        except Exception as e:
            import traceback
            print("\n" + "="*60)
            print(f"ERROR in _plot_internal (auto_refresh={auto_refresh}):")
            print(f"Exception: {e}")
            traceback.print_exc()
            print("="*60 + "\n")
            if not auto_refresh:
                ui.showerror(_('Error'), 
                            _('Error plotting DOS:\n\n') + str(e))
    
    def close(self):
        """Close the dialog."""
        import traceback
        print("\n" + "="*60)
        print("DOSPlotter.close() called")
        print("Stack trace:")
        traceback.print_stack()
        print("="*60 + "\n")
        self.win.close()


def dos_plot_window(gui):
    """Create and show DOS plotting window."""
    # Store reference to prevent garbage collection
    gui.dos_plotter = DOSPlotter(gui)
