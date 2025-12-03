# fmt: off

"""DOS plotting dialog for ASE-GUI with checkbox interface."""

import os
import sys
from pathlib import Path

import ase.gui.ui as ui
from ase.gui.i18n import _


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
        
        # Initialize checkbox states early
        self.element_checks = {}
        self.orbital_checks = {}
        self.tdos_check = None
        self.fill = False
        self.grid = False
        
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
        self.location = ui.Entry(self.default_location, width=50)
        self.win.add([self.location, ui.Button(_('Browse...'), self.browse_directory)])
        
        if self.pdos_files:
            self._build_selection_interface()
        else:
            self.win.add(ui.Label(_('No DOS files found in directory.\n'
                                   'Required: vaspout.h5 OR (INCAR, DOSCAR, PROCAR files)\n'
                                   'Files will be generated automatically if possible.')))
        
        self._add_options_and_customization()
        
        # Buttons - at the very end
        self.win.add([ui.Button(_('Plot'), self.plot),
                     ui.Button(_('Refresh'), self.refresh),
                     ui.Button(_('Close'), self.close)])
    
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
        print(f"DEBUG: Reading DOS files from: {location}")
        print(f"DEBUG: Directory exists: {os.path.isdir(location)}")
        if os.path.isdir(location):
            print(f"DEBUG: Directory contents: {os.listdir(location)[:10]}")  # First 10 files
        
        # First, try to read from vaspout.h5
        if self.HAS_H5PY:
            try:
                self.pdos_files, self.tdos_data = self.read_pdos_from_hdf5(location)
                if self.pdos_files:
                    print(f"DEBUG: Successfully read from vaspout.h5")
            except Exception as e:
                print(f"DEBUG: Failed to read vaspout.h5: {e}")
        
        # Fall back to .dat files if HDF5 reading failed
        if not self.pdos_files:
            print(f"DEBUG: Trying to read PDOS .dat files")
            self.pdos_files = self.read_pdos_files(location)
            if not self.pdos_files:
                # Try to generate PDOS files
                print(f"DEBUG: No .dat files found, trying to generate")
                try:
                    generated = self.try_generate_pdos_dat_files(location)
                    print(f"DEBUG: Generation result: {generated}")
                    if generated:
                        self.pdos_files = self.read_pdos_files(location)
                        print(f"DEBUG: Read files after generation: {self.pdos_files is not None}")
                except Exception as e:
                    print(f"DEBUG: Failed to generate PDOS files: {e}")
                    import traceback
                    traceback.print_exc()
        
        if self.pdos_files:
            self.available_elements = sorted(self.pdos_files.keys())
            print(f"DEBUG: Successfully loaded PDOS for elements: {self.available_elements}")
    
    def _build_selection_interface(self):
        """Build the checkbox interface for element and orbital selection."""
        print(f"DEBUG: Building selection interface with {len(self.available_elements)} elements")
        print(f"DEBUG: Available elements: {self.available_elements}")
        
        self.win.add(_('\nSelect Elements and Orbitals to Plot:'))
        self.win.add(_('(Right-click p or d for individual orbital options)'))
        
        # Add TDOS option
        self.tdos_check = ui.CheckButton(_('TDOS (Total DOS)'))
        self.win.add(self.tdos_check)
        
        # Create a scrollable area for elements if there are many
        self.win.add(_('\nPartial DOS (PDOS):'))
        
        # Available orbitals
        all_orbitals = ['s', 'p', 'd']
        p_individual = ['py', 'pz', 'px']
        d_individual = ['dxy', 'dyz', 'dz2', 'dxz', 'dx2']
        
        # Store context menu bindings to apply later
        self.context_menu_bindings = []
        
        # Create element selection with orbitals
        for element in self.available_elements:
            print(f"DEBUG: Adding element {element}")
            # Element checkbox
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
            
            # Add element with its orbitals in a row
            self.win.add([elem_check] + orbital_checks)
        
        # Attach context menus after window is shown (use after_idle)
        # This ensures widgets are created
        if hasattr(self.win, 'win'):
            self.win.win.after(100, self._attach_all_context_menus)
        
        # Options section (moved above color scheme)
        self.win.add(_('\nOptions:'))
        
        # Spin filter
        self.spin_var = ui.RadioButtons(['Both', 'Up', 'Down'], 
                                        ['both', 'up', 'down'], 
                                        None)
        self.spin_var.value = 'both'
        self.win.add([ui.Label(_('Spin:')), self.spin_var])
        
        # Fill and grid options
        self.fill_check = ui.CheckButton(_('Fill under curves'), False, None)
        self.grid_check = ui.CheckButton(_('Show grid'), False, None)
        self.win.add([self.fill_check, self.grid_check])
        
        # Cutoff
        self.win.add(_('DOS Cutoff (optional):'))
        self.cutoff_entry = ui.Entry('', width=20)
        self.win.add(self.cutoff_entry)
        
        # Color scheme selection (moved below options)
        self.win.add(_('\nColor Scheme:'))
        print(f"DEBUG: Color schemes available: {self.color_schemes}")
        color_options = self.color_schemes
        self.color_scheme_var = ui.RadioButtons(
            [c.upper() for c in color_options],
            color_options,
            None
        )
        # Set VESTA as the default color scheme
        self.color_scheme_var.value = 'vesta' if 'vesta' in self.color_schemes else (self.color_schemes[0] if self.color_schemes else None)
        self.win.add(self.color_scheme_var)
    
    def _attach_all_context_menus(self):
        """Attach all context menus after widgets are created."""
        print(f"DEBUG: Attempting to attach {len(self.context_menu_bindings)} context menus")
        for element, orbital_type, checkbox_widget in self.context_menu_bindings:
            self._attach_context_menu(element, orbital_type, checkbox_widget)
    
    def _attach_context_menu(self, element, orbital_type, checkbox_widget):
        """Attach a right-click context menu to a p or d checkbox."""
        try:
            # CheckButton widgets have a .check attribute after create() is called
            # We need to get the actual tkinter widget
            if hasattr(checkbox_widget, 'check'):
                tk_widget = checkbox_widget.check
            else:
                print(f"DEBUG: CheckButton for {element} {orbital_type} doesn't have .check yet")
                return
            
            def show_context_menu(event):
                self._show_orbital_menu(element, orbital_type, event)
            
            # Bind right-click event (Button-3 on Linux/Windows, Button-2 on macOS)
            tk_widget.bind('<Button-3>', show_context_menu)
            
            print(f"DEBUG: Successfully attached context menu to {element} {orbital_type}")
            
        except Exception as e:
            print(f"DEBUG: Could not attach context menu to {element} {orbital_type}: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_orbital_menu(self, element, orbital_type, event):
        """Show context menu for individual orbital selection."""
        try:
            import tkinter as tk
            
            menu = tk.Menu(tearoff=0)
            
            if orbital_type == 'p':
                individual_orbs = ['py', 'pz', 'px']
                menu_label = 'p-orbital components'
            else:
                individual_orbs = ['dxy', 'dyz', 'dz2', 'dxz', 'dx2']
                menu_label = 'd-orbital components'
            
            # Add label (disabled entry to act as header)
            menu.add_command(label=f"— {menu_label} —", state='disabled')
            menu.add_separator()
            
            # Add checkbuttons for each individual orbital
            for orb in individual_orbs:
                if orb in self.element_checks[element]['individual_orbitals']:
                    check = self.element_checks[element]['individual_orbitals'][orb]
                    menu.add_checkbutton(
                        label=orb,
                        variable=check.var,
                        command=lambda e=element, ot=orbital_type: 
                            self._on_individual_orbital_changed(e, ot)
                    )
            
            menu.add_separator()
            menu.add_command(
                label='Select all',
                command=lambda: self._select_all_individual(element, orbital_type)
            )
            menu.add_command(
                label='Clear all',
                command=lambda: self._clear_all_individual(element, orbital_type)
            )
            
            # Display menu at cursor
            menu.post(event.x_root, event.y_root)
            
        except Exception as e:
            print(f"DEBUG: Error showing orbital menu: {e}")
            import traceback
            traceback.print_exc()
    
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
        self.title_fontsize = ui.SpinBox(14, 8, 30, 1, width=8)
        self.xlabel_fontsize = ui.SpinBox(12, 8, 24, 1, width=8)
        self.ylabel_fontsize = ui.SpinBox(12, 8, 24, 1, width=8)
        
        # Store initial values separately to avoid any mixing
        title_fs_initial = '14'
        xlabel_fs_initial = '12'
        ylabel_fs_initial = '12'
        
        # Title row
        self.show_title_check = ui.CheckButton(_('Title:'), True, None)
        self.title_entry = ui.Entry(default_title, width=35)
        title_fs_label = ui.Label(f'Font (14):')
        self.win.add([self.show_title_check, self.title_entry, title_fs_label, self.title_fontsize])
        
        # X-axis row
        self.show_xlabel_check = ui.CheckButton(_('X-axis:'), True, None)
        self.xlabel_entry = ui.Entry('Energy (eV)', width=35)
        xlabel_fs_label = ui.Label(f'Font (12):')
        self.win.add([self.show_xlabel_check, self.xlabel_entry, xlabel_fs_label, self.xlabel_fontsize])
        
        # Y-axis row
        self.show_ylabel_check = ui.CheckButton(_('Y-axis:'), True, None)
        self.ylabel_entry = ui.Entry('Density of States', width=35)
        ylabel_fs_label = ui.Label(f'Font (12):')
        self.win.add([self.show_ylabel_check, self.ylabel_entry, ylabel_fs_label, self.ylabel_fontsize])
        
        self.win.add(_(''))  # Empty line separator
    
    def browse_directory(self):
        """Open directory browser."""
        from tkinter.filedialog import askdirectory
        directory = askdirectory(initialdir=self.location.value,
                                title=_('Select DOS Data Directory'))
        if directory:
            self.location.value = directory
    
    def refresh(self):
        """Refresh DOS files from the selected directory."""
        location = self.location.value.strip()
        if not os.path.isdir(location):
            ui.showerror(_('Error'), _('Directory does not exist.'))
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
        """Execute DOS plotting."""
        if not self.pdos_files:
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
        
        # Get cutoff
        cutoff = None
        cutoff_str = self.cutoff_entry.value.strip()
        if cutoff_str:
            try:
                cutoff = float(cutoff_str)
            except ValueError:
                ui.showerror(_('Error'), _('Invalid cutoff value.'))
                return
        
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
        
        location = self.location.value.strip()
        
        # Plot
        try:
            self.plot_pdos(self.pdos_files, plotting_info, title, 
                          spin_filter=spin_filter, fill=fill, location=location, 
                          fill_colors=fill_colors, cutoff=cutoff, show_grid=show_grid, 
                          xlabel=xlabel, ylabel=ylabel, 
                          title_fontsize=title_fontsize, 
                          xlabel_fontsize=xlabel_fontsize, 
                          ylabel_fontsize=ylabel_fontsize)
        except Exception as e:
            ui.showerror(_('Error'), 
                        _('Error plotting DOS:\n\n') + str(e))
            import traceback
            traceback.print_exc()
    
    def close(self):
        """Close the dialog."""
        self.win.close()


def dos_plot_window(gui):
    """Create and show DOS plotting window."""
    DOSPlotter(gui)
