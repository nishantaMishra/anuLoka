# GUI for plotting potentials (LOCPOT-based)

import os
import sys
from pathlib import Path
import subprocess
from functools import partial

import tkinter as tk

import ase.gui.ui as ui
from ase.gui.i18n import _

import matplotlib.pyplot as plt


def parse_outcar_fermi(outcar_path: str):
    """Parse OUTCAR for the last occurrence of E-fermi and return float or None."""
    if not os.path.isfile(outcar_path):
        return None
    last_val = None
    try:
        with open(outcar_path, 'r', errors='ignore') as f:
            for line in f:
                if 'E-fermi' in line:
                    # Try to extract numeric token after 'E-fermi'
                    # Line formats vary; find 'E-fermi' and then ':' and number
                    try:
                        idx = line.index('E-fermi')
                        tail = line[idx:]
                        # split by colon or whitespace
                        parts = tail.replace(':', ' ').split()
                        # parts[0] == 'E-fermi'
                        for token in parts[1:]:
                            try:
                                val = float(token)
                                last_val = val
                                break
                            except Exception:
                                continue
                    except ValueError:
                        continue
    except Exception:
        return None
    return last_val


class PotentialPlotter:
    """Dialog for plotting electrostatic potential from LOCPOT files."""

    def __init__(self, gui):
        self.gui = gui
        self.win = ui.Window(_('Plot Potential'))

        self.default_location = self._get_default_location()

        # LOCPOT file path (moved above Plot Type)
        self.win.add(_('LOCPOT file:'))
        self.loc_entry = ui.Entry(os.path.join(self.default_location, 'LOCPOT'), width=50)
        self.win.add([self.loc_entry, ui.Button(_('Browse...'), self.browse_file)])

        # Plot type dropdown with space for axis (axis shown only for Planar-Average)
        # First entry is a placeholder so users must actively choose a plot type
        self._placeholder_type = _('Select Plot Type...')
        types = [
            self._placeholder_type,
            'Slice of Potential',
            'Linear-Average Potential',
            'Potential Along Specified Path',
            'Planar-Average Potential',
            'Macroscopic-Average Potential'
        ]
        # Use ComboBox for selection
        self.type_combo = ui.ComboBox(types, types, callback=self._on_type_change)
        
        # Create axis selection (shown conditionally for Planar-Average)
        self.axis_label = ui.Label(_('  Axis:'))
        self.axis_combo = ui.ComboBox(['x', 'y', 'z'], ['a', 'b', 'c'], callback=None)
        
        # Add Plot Type label and combo
        self.win.add([ui.Label(_('Plot Type:')), self.type_combo, self.axis_label, self.axis_combo])

        # Area where type-specific options are placed
        self.options_rows = ui.Rows()
        self.win.add(self.options_rows)

        # Area for plot customization (appears after type selection)
        self.custom_rows = ui.Rows()
        self.win.add(self.custom_rows)

        # Buttons
        self.win.add([ui.Button(_('Plot'), self.plot), ui.Button(_('Close'), self.close)])

        # Do not show customization until the user actively selects a plot type.
        # Show a prompt in the options area instead.
        self.options_rows.add(_('Please select a plot type to show options.'))
        
        # Initially hide axis widgets completely using pack_forget
        try:
            if hasattr(self, 'axis_label') and hasattr(self.axis_label, 'widget'):
                self.axis_label.widget.pack_forget()
            if hasattr(self, 'axis_combo') and hasattr(self.axis_combo, 'widget'):
                self.axis_combo.widget.pack_forget()
        except Exception:
            pass

    def _get_default_location(self):
        if hasattr(self.gui, 'workspace_dir') and self.gui.workspace_dir:
            return self.gui.workspace_dir

        if hasattr(self.gui, 'images') and hasattr(self.gui.images, 'filenames'):
            try:
                current_file = self.gui.images.filenames[self.gui.frame]
                if current_file:
                    if '@' in current_file:
                        current_file = current_file.split('@')[0]
                    return os.path.dirname(os.path.abspath(current_file))
            except Exception:
                pass

        return os.getcwd()

    def browse_file(self):
        from tkinter.filedialog import askopenfilename
        initial = self.loc_entry.value.strip() or self.default_location
        path = askopenfilename(parent=getattr(self.win, 'win', None), initialdir=initial, title=_('Select LOCPOT file'))
        if path:
            self.loc_entry.value = path

    def _on_type_change(self, value):
        # Clear existing option rows
        self.options_rows.clear()

        # Update customization widgets for any selected type
        try:
            self._add_options_and_customization()
        except Exception:
            pass

        # Value is one of the labels; check for Planar-Average
        if value == 'Planar-Average Potential':
            # Show axis selection using pack()
            try:
                if hasattr(self, 'axis_label') and hasattr(self.axis_label, 'widget'):
                    self.axis_label.widget.pack(side='left')
                if hasattr(self, 'axis_combo') and hasattr(self.axis_combo, 'widget'):
                    self.axis_combo.widget.pack(side='left')
            except Exception:
                pass
            
            # Add planar-specific checkboxes (default: unchecked)
            try:
                self.show_vac_check = ui.CheckButton(_('Show Vacuum level'), False, None)
                self.show_fermi_check = ui.CheckButton(_('Show Fermi level'), False, None)
                self.show_wf_check = ui.CheckButton(_('Show Work function'), False, None)
                self.options_rows.add([self.show_vac_check, self.show_fermi_check, self.show_wf_check])
                
                # Add entry fields to display computed values
                self.vac_value_entry = ui.Entry('', width=15)
                self.fermi_value_entry = ui.Entry('', width=15)
                self.wf_value_entry = ui.Entry('', width=15)
                self.options_rows.add([self.vac_value_entry, self.fermi_value_entry, self.wf_value_entry])
            except Exception:
                pass
        else:
            # Hide axis selection using pack_forget()
            try:
                if hasattr(self, 'axis_label') and hasattr(self.axis_label, 'widget'):
                    self.axis_label.widget.pack_forget()
                if hasattr(self, 'axis_combo') and hasattr(self.axis_combo, 'widget'):
                    self.axis_combo.widget.pack_forget()
            except Exception:
                pass
            # For now, show a short helper text for other types
            self.options_rows.add(_('Selected plot type will show its options here.'))

    def _add_options_and_customization(self):
        """Create plot customization UI similar to Plot DOS."""
        # Clear previous customization rows
        self.custom_rows.clear()

        self.custom_rows.add('\nPlot Customization:')

        # Title
        default_title = ''
        if self.default_location:
            try:
                last_dirs = os.path.normpath(self.default_location).split(os.sep)[-4:]
                default_title = os.path.join(*last_dirs)
            except Exception:
                default_title = ''

        self.show_title_check = ui.CheckButton(_('Title:'), True, None)
        self.title_entry = ui.Entry(default_title, width=35)
        self.title_fontsize = ui.SpinBox(14, 8, 30, 1, width=4)
        self.custom_rows.add([self.show_title_check, self.title_entry, self.title_fontsize])

        # X-axis
        self.show_xlabel_check = ui.CheckButton(_('X-axis:'), True, None)
        self.xlabel_entry = ui.Entry('Position (Å)', width=20)
        self.xlabel_fontsize = ui.SpinBox(12, 8, 24, 1, width=3)
        xlim_label = ui.Label('  xlim:')
        self.xlim_min = ui.SpinBox(0, -1000, 1000, 1, width=4)
        self.xlim_max = ui.SpinBox(0, -1000, 1000, 1, width=4)
        self.custom_rows.add([self.show_xlabel_check, self.xlabel_entry, self.xlabel_fontsize, xlim_label, self.xlim_min, self.xlim_max])

        # Y-axis
        self.show_ylabel_check = ui.CheckButton(_('Y-axis:'), True, None)
        self.ylabel_entry = ui.Entry('Potential (eV)', width=20)
        self.ylabel_fontsize = ui.SpinBox(12, 8, 24, 1, width=3)
        ylim_label = ui.Label('  ylim:')
        self.ylim_min = ui.SpinBox(0, -1000, 1000, 1, width=4)
        self.ylim_max = ui.SpinBox(0, -1000, 1000, 1, width=4)
        self.custom_rows.add([self.show_ylabel_check, self.ylabel_entry, self.ylabel_fontsize, ylim_label, self.ylim_min, self.ylim_max])

        # Fill and grid options
        self.fill_check = ui.CheckButton(_('Fill under curve'), False, None)
        self.grid_check = ui.CheckButton(_('Show grid'), False, None)
        self.custom_rows.add([self.fill_check, self.grid_check])

        # Best-effort tooltip bindings
        try:
            if hasattr(self.title_fontsize, 'widget'):
                self.title_fontsize.widget.bind('<Enter>', lambda e: self._show_tooltip(e, 'Font size'))
                self.title_fontsize.widget.bind('<Leave>', lambda e: self._hide_tooltip())
        except Exception:
            pass

    def _show_tooltip(self, event, text):
        try:
            import tkinter as tk
            self.tooltip = tk.Toplevel()
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(self.tooltip, text=text, background="#ffffe0",
                           relief='solid', borderwidth=1, padx=5, pady=2)
            label.pack()
        except Exception:
            pass

    def _hide_tooltip(self):
        try:
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()
                del self.tooltip
        except Exception:
            pass

    def plot(self):
        plot_type = self.type_combo.value
        loc = self.loc_entry.value.strip()
        if not loc or not os.path.isfile(loc):
            ui.showerror(_('Error'), _('LOCPOT file not found.'))
            return

        # If Planar-Average selected, call LOCPOT planar average routine
        if plot_type == 'Planar-Average Potential':
            # axis_combo stores values ['a','b','c'] mapping to x,y,z
            direction = self.axis_combo.value
            try:
                # Ensure repository root is on sys.path so we can import the helper
                repo_root = Path(__file__).parents[2]
                if str(repo_root) not in sys.path:
                    sys.path.insert(0, str(repo_root))

                from initial_code.LOCPOT_planar_avg import read_loCPOT_planar_average
            except Exception as e:
                ui.showerror(_('Error'), _('Could not import LOCPOT helper:\n') + str(e))
                return

            try:
                z, vz, meta = read_loCPOT_planar_average(loc, direction=direction)
            except Exception as e:
                ui.showerror(_('Error'), _('Error reading LOCPOT:\n') + str(e))
                return
            # Plot using Matplotlib and apply customization options when present
            try:
                # Read customization options (if created)
                title = None
                xlabel = meta.get('axis_label', 'position (Å)')
                ylabel = _('Planar-averaged electrostatic potential (eV)')
                title_fs = 14
                xlabel_fs = 12
                ylabel_fs = 12
                show_grid = True
                fill = False
                xlim = None
                ylim = None

                if hasattr(self, 'show_title_check') and self.show_title_check.var.get():
                    title = self.title_entry.value.strip()
                if hasattr(self, 'show_xlabel_check') and self.show_xlabel_check.var.get():
                    xlabel = self.xlabel_entry.value.strip()
                if hasattr(self, 'show_ylabel_check') and self.show_ylabel_check.var.get():
                    ylabel = self.ylabel_entry.value.strip()
                if hasattr(self, 'title_fontsize'):
                    try:
                        title_fs = self.title_fontsize.value
                    except Exception:
                        title_fs = title_fs
                if hasattr(self, 'xlabel_fontsize'):
                    try:
                        xlabel_fs = self.xlabel_fontsize.value
                    except Exception:
                        xlabel_fs = xlabel_fs
                if hasattr(self, 'ylabel_fontsize'):
                    try:
                        ylabel_fs = self.ylabel_fontsize.value
                    except Exception:
                        ylabel_fs = ylabel_fs
                if hasattr(self, 'grid_check'):
                    show_grid = self.grid_check.var.get()
                if hasattr(self, 'fill_check'):
                    fill = self.fill_check.var.get()
                if hasattr(self, 'xlim_min') and hasattr(self, 'xlim_max'):
                    try:
                        xmin = self.xlim_min.value
                        xmax = self.xlim_max.value
                        if xmin < xmax:
                            xlim = (xmin, xmax)
                        else:
                            xlim = None
                    except Exception:
                        xlim = None
                if hasattr(self, 'ylim_min') and hasattr(self, 'ylim_max'):
                    try:
                        ymin = self.ylim_min.value
                        ymax = self.ylim_max.value
                        if ymin < ymax:
                            ylim = (ymin, ymax)
                        else:
                            ylim = None
                    except Exception:
                        ylim = None

                # Always compute vacuum level for Planar-Average
                vacuum_level = None
                work_function = None
                try:
                    # Map axis value ('a','b','c') to vaspkit input (1,2,3)
                    axis_map = {'a': '1', 'b': '2', 'c': '3'}
                    axis_input = axis_map.get(direction, '3')
                    
                    loc_dir = os.path.dirname(loc) or os.getcwd()
                    # Execute vaspkit: 42 -> 426 -> axis
                    cmd = f'(echo 42; sleep 0.5; echo 426; sleep 0.5; echo {axis_input}) | vaspkit'
                    result = subprocess.run(cmd, shell=True, cwd=loc_dir, 
                                          capture_output=True, text=True, timeout=30)
                    
                    # Parse stdout for "Vacuum-Level (eV): X.XXX" and "Work Function (eV): Y.YYY"
                    for line in result.stdout.split('\n'):
                        if 'Vacuum-Level (eV):' in line:
                            try:
                                parts = line.split(':')
                                vacuum_level = float(parts[1].strip())
                            except Exception:
                                pass
                        if 'Work Function (eV):' in line:
                            try:
                                parts = line.split(':')
                                work_function = float(parts[1].strip())
                            except Exception:
                                pass
                    
                    # Update the entry field with the value
                    if vacuum_level is not None and hasattr(self, 'vac_value_entry'):
                        self.vac_value_entry.value = f'{vacuum_level:.4f} eV'
                    elif hasattr(self, 'vac_value_entry'):
                        self.vac_value_entry.value = 'N/A'
                    
                    # Update work function entry field
                    if work_function is not None and hasattr(self, 'wf_value_entry'):
                        self.wf_value_entry.value = f'{work_function:.4f} eV'
                    elif hasattr(self, 'wf_value_entry'):
                        self.wf_value_entry.value = 'N/A'
                except Exception as e:
                    print(f"Warning: Could not get vacuum level from vaspkit: {e}")
                    vacuum_level = None
                    work_function = None
                    if hasattr(self, 'vac_value_entry'):
                        self.vac_value_entry.value = 'N/A'
                    if hasattr(self, 'wf_value_entry'):
                        self.wf_value_entry.value = 'N/A'

                # Always read Fermi from OUTCAR for Planar-Average
                fermi_level = None
                try:
                    loc_dir = os.path.dirname(loc) or os.getcwd()
                    outcar_path = os.path.join(loc_dir, 'OUTCAR')
                    fermi_level = parse_outcar_fermi(outcar_path)
                    
                    # Update the entry field with the value
                    if fermi_level is not None and hasattr(self, 'fermi_value_entry'):
                        self.fermi_value_entry.value = f'{fermi_level:.4f} eV'
                    elif hasattr(self, 'fermi_value_entry'):
                        self.fermi_value_entry.value = 'N/A'
                except Exception:
                    fermi_level = None
                    if hasattr(self, 'fermi_value_entry'):
                        self.fermi_value_entry.value = 'N/A'

                plt.figure()
                if fill:
                    plt.fill_between(z, vz, alpha=0.3)
                plt.plot(z, vz)
                if xlabel is not None:
                    plt.xlabel(xlabel, fontsize=xlabel_fs)
                if ylabel is not None:
                    plt.ylabel(ylabel, fontsize=ylabel_fs)
                if title is not None:
                    plt.title(title, fontsize=title_fs)
                if show_grid:
                    plt.grid(True, alpha=0.3)
                # Plot vacuum and fermi levels only if checkboxes are checked
                if vacuum_level is not None and hasattr(self, 'show_vac_check') and self.show_vac_check.var.get():
                    plt.axhline(vacuum_level, color='orange', linestyle='--', label=_('Vacuum level'))
                if fermi_level is not None and hasattr(self, 'show_fermi_check') and self.show_fermi_check.var.get():
                    plt.axhline(fermi_level, color='red', linestyle=':', label=_('Fermi level'))
                # Note: Work function is a scalar difference, not typically plotted as a line
                # But if user wants to see it as annotation or line, can be added here
                if xlim is not None:
                    plt.xlim(xlim)
                if ylim is not None:
                    plt.ylim(ylim)
                plt.tight_layout()
                # Show legend only if at least one line is plotted
                show_legend = False
                if hasattr(self, 'show_vac_check') and self.show_vac_check.var.get() and vacuum_level is not None:
                    show_legend = True
                if hasattr(self, 'show_fermi_check') and self.show_fermi_check.var.get() and fermi_level is not None:
                    show_legend = True
                # Work function as text annotation if checked
                if hasattr(self, 'show_wf_check') and self.show_wf_check.var.get() and work_function is not None:
                    # Add work function as text annotation in the plot
                    plt.text(0.02, 0.98, f'Work Function: {work_function:.4f} eV', 
                            transform=plt.gca().transAxes, verticalalignment='top',
                            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
                if show_legend:
                    plt.legend()
                plt.show()
            except Exception as e:
                ui.showerror(_('Error'), _('Error plotting potential:\n') + str(e))
                return
        else:
            ui.showinfo(_('Info'), _('Plot type not implemented yet.'))

    def close(self):
        self.win.close()


def potential_plot_window(gui):
    PotentialPlotter(gui)
