# Qt version of GUI for plotting potentials (LOCPOT-based)

import os
import sys
from pathlib import Path
import subprocess
from functools import partial
import numpy as np

from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

import ase.gui.ui_qt as ui
from ase.gui.i18n import _

import matplotlib
matplotlib.use('Qt5Agg')
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
        self.loc_entry = ui.Entry(os.path.join(self.default_location, 'LOCPOT'), width=35)
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
        
        # Add Plot Type combo (label redundant; combo already indicates its purpose)
        # Place combo at the left so it's the first control on the row
        self.win.add([self.type_combo, self.axis_label, self.axis_combo])

        # Area where type-specific options are placed
        self.options_rows = ui.Rows()
        self.win.add(self.options_rows)

        # Area for plot customization (appears after type selection)
        self.custom_rows = ui.Rows()
        self.win.add(self.custom_rows)

        # Live preview checkbox (disabled until user selects a plot type)
        self.auto_preview_check = ui.CheckButton(_('Live preview'), False, self._toggle_auto_preview)

        # For auto-preview debouncing and reusing plots
        self._update_pending = False
        self.plot_figure = None
        self.plot_axes = None
        self._text_debounce_timer = None
        # Cache for loaded LOCPOT planar-average data to avoid reloading on trivial changes
        self._cached_loc = None
        self._cached_direction = None
        self._cached_z = None
        self._cached_vz = None
        self._cached_meta = None
        self._preview_handlers_connected = False
        # Plot handles and cached markers for fast refresh
        self._main_line = None
        self._vac_line = None
        self._fermi_line = None
        self._wf_annotation = None
        self._fill_collection = None
        self._cached_vacuum = None
        self._cached_work = None
        self._cached_fermi = None
        # Cache for linear-average results
        self._cached_lavg_loc = None
        self._cached_lavg_plane = None
        self._cached_lavg_rep_a = None
        self._cached_lavg_rep_b = None
        self._cached_lavg_x = None
        self._cached_lavg_v = None
        self._cached_lavg_meta = None
        # Cache for macroscopic-average results
        self._cached_macro_loc = None
        self._cached_macro_axis = None
        self._cached_macro_period = None
        self._cached_macro_iter = None
        self._cached_macro_z = None
        self._cached_macro_vmacro = None
        self._cached_macro_vplanar = None
        self._cached_macro_meta = None

        # Buttons
        self.plot_button = ui.Button(_('Plot'), self.plot)
        self.win.add([self.auto_preview_check, self.plot_button, ui.Button(_('Close'), self.close)])

        # Do not show customization until the user actively selects a plot type.
        # Show a prompt in the options area instead.
        self.options_rows.add(_('Please select a plot type to show options.'))

        # Initially hide axis widgets (only shown for planar/macro types)
        self._set_axis_visible(False)

    def _set_axis_visible(self, visible):
        """Show/hide axis selection widgets regardless of layout manager."""
        try:
            if hasattr(self, 'axis_label') and hasattr(self.axis_label, 'widget'):
                self.axis_label.widget.setVisible(visible)
            if hasattr(self, 'axis_combo') and hasattr(self.axis_combo, 'widget'):
                self.axis_combo.widget.setVisible(visible)
        except Exception:
            pass

    def _compact_checkbox(self, checkbox):
        try:
            if hasattr(checkbox, 'widget') and checkbox.widget:
                checkbox.widget.setFixedWidth(22)
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
        from PyQt5.QtWidgets import QFileDialog
        initial = self.loc_entry.value.strip() or self.default_location
        parent_widget = getattr(self.win, 'win', None)
        path, _filter = QFileDialog.getOpenFileName(parent_widget, _('Select LOCPOT file'), initial)
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

        show_axis = value in ('Planar-Average Potential', 'Macroscopic-Average Potential')
        self._set_axis_visible(show_axis)

        if value == 'Planar-Average Potential':
            try:
                # Use compact checkbox + separate label so tooltip applies to the box only
                self.show_vac_check = ui.CheckButton('', False, None)
                self._compact_checkbox(self.show_vac_check)
                vac_label = ui.Label(_('Vacuum level'))

                self.show_fermi_check = ui.CheckButton('', False, None)
                self._compact_checkbox(self.show_fermi_check)
                fermi_label = ui.Label(_('Fermi level'))

                self.show_wf_check = ui.CheckButton('', False, None)
                self._compact_checkbox(self.show_wf_check)
                wf_label = ui.Label(_('Work function'))

                self.vac_value_entry = ui.Entry('  ', width=10)
                self.fermi_value_entry = ui.Entry('', width=10)
                self.wf_value_entry = ui.Entry('', width=10)

                # Vertical stacks for each parameter
                vac_col = ui.Rows([[self.show_vac_check, vac_label], [self.vac_value_entry]])
                fermi_col = ui.Rows([[self.show_fermi_check, fermi_label], [self.fermi_value_entry]])
                wf_col = ui.Rows([[self.show_wf_check, wf_label], [self.wf_value_entry]])

                # Add the three columns side-by-side
                self.options_rows.add([vac_col, fermi_col, wf_col])

                # Tooltips for Planar-Average checkboxes (best-effort)
                try:
                    if hasattr(self, 'show_vac_check') and hasattr(self.show_vac_check, 'widget'):
                        self.show_vac_check.widget.setToolTip(_('Show Vacuum level'))
                    if hasattr(self, 'show_fermi_check') and hasattr(self.show_fermi_check, 'widget'):
                        self.show_fermi_check.widget.setToolTip(_('Show Fermi level'))
                    if hasattr(self, 'show_wf_check') and hasattr(self.show_wf_check, 'widget'):
                        self.show_wf_check.widget.setToolTip(_('Show Work function'))
                except Exception:
                    pass
            except Exception:
                pass
        elif value == 'Linear-Average Potential':
            try:
                self.plane_label = ui.Label(_('Plane:'))
                self.plane_combo = ui.ComboBox(['ab', 'ac', 'bc'], ['ab', 'ac', 'bc'], callback=None)
                self.rep_label = ui.Label(_('Repeat (a b):'))
                self.rep_a_entry = ui.Entry('1', width=4)
                self.rep_b_entry = ui.Entry('1', width=4)
                self.options_rows.add([self.plane_label, self.plane_combo, self.rep_label, self.rep_a_entry, self.rep_b_entry])
            except Exception:
                pass
        elif value == 'Macroscopic-Average Potential':
            try:
                self.period_label = ui.Label(_('Period length (Å):'))
                self.period_entry = ui.Entry('2.0', width=6)
                self.iter_label = ui.Label(_('Iterations:'))
                self.iter_entry = ui.Entry('2', width=4)
                self.options_rows.add([self.period_label, self.period_entry, self.iter_label, self.iter_entry])
            except Exception:
                pass
        else:
            self.options_rows.add(_('Selected plot type will show its options here.'))

    def _add_options_and_customization(self):
        """Create plot customization UI similar to Plot DOS."""
        # Clear previous customization rows
        self.custom_rows.clear()

        self.custom_rows.add('\nPlot Customization:')

        default_title = ''
        if getattr(self, 'default_location', None):
            try:
                last_dirs = os.path.normpath(self.default_location).split(os.sep)[-4:]
                default_title = os.path.join(*last_dirs)
            except Exception:
                default_title = ''

        self.show_title_check = ui.CheckButton('', True, None)
        self._compact_checkbox(self.show_title_check)
        title_label = ui.Label(_('Title:'))
        self.title_entry = ui.Entry(default_title, width=34)
        self.title_fontsize = ui.SpinBox(14, 8, 30, 1, width=4)
        self.custom_rows.add([self.show_title_check, title_label, self.title_entry, self.title_fontsize])

        self.show_xlabel_check = ui.CheckButton('', True, None)
        self._compact_checkbox(self.show_xlabel_check)
        xlabel_label = ui.Label(_('X-axis:'))
        self.xlabel_entry = ui.Entry('Position (Å)', width=18)
        self.xlabel_fontsize = ui.SpinBox(12, 8, 24, 1, width=3)
        xlim_label = ui.Label(_('xlim:'))
        self.xlim_min = ui.SpinBox(0, -1000, 1000, 1, width=4)
        self.xlim_max = ui.SpinBox(0, -1000, 1000, 1, width=4)
        self.custom_rows.add([
            self.show_xlabel_check, xlabel_label, self.xlabel_entry,
            self.xlabel_fontsize, xlim_label, self.xlim_min, self.xlim_max
        ])

        self.show_ylabel_check = ui.CheckButton('', True, None)
        self._compact_checkbox(self.show_ylabel_check)
        ylabel_label = ui.Label(_('Y-axis:'))
        self.ylabel_entry = ui.Entry('Potential (eV)', width=18)
        self.ylabel_fontsize = ui.SpinBox(12, 8, 24, 1, width=3)
        ylim_label = ui.Label(_('ylim:'))
        self.ylim_min = ui.SpinBox(0, -1000, 1000, 1, width=4)
        self.ylim_max = ui.SpinBox(0, -1000, 1000, 1, width=4)
        self.custom_rows.add([
            self.show_ylabel_check, ylabel_label, self.ylabel_entry,
            self.ylabel_fontsize, ylim_label, self.ylim_min, self.ylim_max
        ])

        self.fill_check = ui.CheckButton(_('Fill under curve'), False, None)
        self.grid_check = ui.CheckButton(_('Show grid'), False, None)
        self.custom_rows.add([self.fill_check, self.grid_check])

        # Set tooltips using Qt's native method
        try:
            if hasattr(self, 'title_fontsize') and hasattr(self.title_fontsize, 'widget'):
                self.title_fontsize.widget.setToolTip('Font size')
            # NEW: tooltips for x/y axis limits
            if hasattr(self, 'xlim_min') and hasattr(self.xlim_min, 'widget'):
                self.xlim_min.widget.setToolTip('X-axis minimum')
            if hasattr(self, 'xlim_max') and hasattr(self.xlim_max, 'widget'):
                self.xlim_max.widget.setToolTip('X-axis maximum')
            if hasattr(self, 'ylim_min') and hasattr(self.ylim_min, 'widget'):
                self.ylim_min.widget.setToolTip('Y-axis minimum')
            if hasattr(self, 'ylim_max') and hasattr(self.ylim_max, 'widget'):
                self.ylim_max.widget.setToolTip('Y-axis maximum')

            # NEW: tooltips for Title / X-axis / Y-axis checkboxes
            if hasattr(self, 'show_title_check') and hasattr(self.show_title_check, 'widget'):
                try:
                    self.show_title_check.widget.setToolTip(_('Show Plot Title'))
                except Exception:
                    pass
            if hasattr(self, 'show_xlabel_check') and hasattr(self.show_xlabel_check, 'widget'):
                try:
                    self.show_xlabel_check.widget.setToolTip(_('Show X-axis title'))
                except Exception:
                    pass
            if hasattr(self, 'show_ylabel_check') and hasattr(self.show_ylabel_check, 'widget'):
                try:
                    self.show_ylabel_check.widget.setToolTip(_('Show Y-axis title'))
                except Exception:
                    pass

        except Exception:
            pass
        # If live preview is enabled, (re)connect handlers for newly created widgets
        try:
            if getattr(self, 'auto_preview_check', None) and self.auto_preview_check.var.get():
                try:
                    self._connect_auto_preview_handlers()
                except Exception:
                    pass
        except Exception:
            pass

    def _show_tooltip(self, event, text):
        try:
            from PyQt5.QtWidgets import QToolTip
            from PyQt5.QtCore import QPoint
            from PyQt5.QtGui import QCursor
            QToolTip.showText(QCursor.pos(), text)
        except Exception:
            pass

    def _hide_tooltip(self):
        try:
            from PyQt5.QtWidgets import QToolTip
            QToolTip.hideText()
        except Exception:
            pass

    def _toggle_auto_preview(self, enabled=None):
        """Enable/disable live preview. Uses a QTimer to detect input changes."""
        try:
            if enabled is None:
                # Called from ui.CheckButton without args
                enabled = self.auto_preview_check.var.get() if hasattr(self, 'auto_preview_check') else False

            if enabled:
                # Start timer
                self._preview_timer = QTimer()
                self._preview_timer.setInterval(700)
                self._preview_timer.timeout.connect(self._auto_preview_tick)
                # Snapshot initial state
                self._last_preview_state = None
                self._preview_timer.start()
                # Connect widget change handlers for faster, event-driven updates
                try:
                    self._connect_auto_preview_handlers()
                except Exception:
                    pass
            else:
                # Stop and delete timer
                if hasattr(self, '_preview_timer'):
                    try:
                        self._preview_timer.stop()
                    except Exception:
                        pass
                    try:
                        del self._preview_timer
                    except Exception:
                        pass
                self._last_preview_state = None
                try:
                    # Disconnect handlers if we set them
                    self._disconnect_auto_preview_handlers()
                except Exception:
                    pass
        except Exception:
            pass

    def _auto_preview_tick(self):
        """Called periodically when live preview enabled. Triggers plot when inputs changed."""
        try:
            # Build current state tuple
            state = []
            try:
                state.append(self.loc_entry.value.strip())
            except Exception:
                state.append(None)
            try:
                state.append(self.type_combo.value)
            except Exception:
                state.append(None)
            try:
                state.append(self.axis_combo.value)
            except Exception:
                state.append(None)
            try:
                plane_val = getattr(getattr(self, 'plane_combo', None), 'value', None)
                state.append(plane_val)
            except Exception:
                state.append(None)
            for rep_attr in ('rep_a_entry', 'rep_b_entry'):
                try:
                    ent = getattr(self, rep_attr, None)
                    state.append(ent.value if ent else None)
                except Exception:
                    state.append(None)
            try:
                period_val = getattr(getattr(self, 'period_entry', None), 'value', None)
                state.append(period_val)
            except Exception:
                state.append(None)
            try:
                iter_val = getattr(getattr(self, 'iter_entry', None), 'value', None)
                state.append(iter_val)
            except Exception:
                state.append(None)
            # include checkboxes and key entries
            for attr in ('show_vac_check', 'show_fermi_check', 'show_wf_check'):
                try:
                    chk = getattr(self, attr, None)
                    state.append(bool(chk.var.get()))
                except Exception:
                    state.append(None)
            try:
                title = self.title_entry.value.strip() if hasattr(self, 'title_entry') else None
                state.append(title)
            except Exception:
                state.append(None)

            state = tuple(state)

            if state != getattr(self, '_last_preview_state', None):
                self._last_preview_state = state
                # Debounce and schedule an auto-plot (will check cache)
                self._schedule_auto_plot()
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
            except Exception:
                pass

            # Use a background QThread to avoid blocking the UI while parsing LOCPOT
            class LOCPOTWorker(QThread):
                result = pyqtSignal(object, object, object)
                error = pyqtSignal(str)

                def __init__(self, path, direction):
                    super().__init__()
                    self.path = path
                    self.direction = direction

                def run(self):
                    try:
                        from initial_code.LOCPOT_planar_avg import read_loCPOT_planar_average
                        z, vz, meta = read_loCPOT_planar_average(self.path, direction=self.direction)
                        self.result.emit(z, vz, meta)
                    except Exception as e:
                        self.error.emit(str(e))

            # Disable UI and show busy cursor
            try:
                if hasattr(self.plot_button, 'widget'):
                    self.plot_button.widget.setEnabled(False)
            except Exception:
                pass
            QApplication.setOverrideCursor(Qt.WaitCursor)

            self._locpot_worker = LOCPOTWorker(loc, direction)

            def on_error(msg):
                QApplication.restoreOverrideCursor()
                try:
                    if hasattr(self.plot_button, 'widget'):
                        self.plot_button.widget.setEnabled(True)
                except Exception:
                    pass
                ui.showerror(_('Error'), _('Error reading LOCPOT:\n') + str(msg))

            def on_result(z, vz, meta):
                QApplication.restoreOverrideCursor()
                try:
                    if hasattr(self.plot_button, 'widget'):
                        self.plot_button.widget.setEnabled(True)
                except Exception:
                    pass
                # Cache loaded data to speed up subsequent preview updates
                try:
                    self._cached_loc = loc
                    self._cached_direction = direction
                    self._cached_z = z
                    self._cached_vz = vz
                    self._cached_meta = meta
                    # reset cached marker values; will be computed on explicit Plot
                    self._cached_vacuum = None
                    self._cached_work = None
                    self._cached_fermi = None
                except Exception:
                    pass
                # Continue plotting on the main thread
                try:
                    self._plot_planar_avg(z, vz, meta)
                except Exception as e:
                    ui.showerror(_('Error'), _('Error plotting potential:\n') + str(e))
            def on_finished():
                # Ensure we release our reference so the QThread object can be
                # garbage-collected after it has finished running.
                try:
                    if hasattr(self.plot_button, 'widget'):
                        self.plot_button.widget.setEnabled(True)
                except Exception:
                    pass
                QApplication.restoreOverrideCursor()
                try:
                    self._locpot_worker = None
                except Exception:
                    pass

            self._locpot_worker.error.connect(on_error)
            self._locpot_worker.result.connect(on_result)
            self._locpot_worker.finished.connect(on_finished)
            self._locpot_worker.start()
            return
        elif plot_type == 'Linear-Average Potential':
            try:
                plane = 'ab'
                if hasattr(self, 'plane_combo'):
                    plane = self.plane_combo.value
                plane_map = {'ab': '1', 'ac': '2', 'bc': '3'}
                plane_input = plane_map.get(plane, '1')

                try:
                    rep_a = int(self.rep_a_entry.value) if hasattr(self, 'rep_a_entry') else 1
                except Exception:
                    rep_a = 1
                try:
                    rep_b = int(self.rep_b_entry.value) if hasattr(self, 'rep_b_entry') else 1
                except Exception:
                    rep_b = 1

                loc_dir = os.path.dirname(loc) or os.getcwd()

                class LinearAvgWorker(QThread):
                    result = pyqtSignal(object, object, object)
                    error = pyqtSignal(str)

                    def __init__(self, path, plane_code, rep_a_val, rep_b_val, plane_label, cwd):
                        super().__init__()
                        self.path = path
                        self.plane_code = plane_code
                        self.rep_a_val = rep_a_val
                        self.rep_b_val = rep_b_val
                        self.plane_label = plane_label
                        self.cwd = cwd

                    def run(self):
                        try:
                            cmd = f'(echo 42; sleep 0.5; echo 422; sleep 0.5; echo {self.plane_code}; sleep 0.5; echo "{self.rep_a_val} {self.rep_b_val}") | vaspkit'
                            result = subprocess.run(cmd, shell=True, cwd=self.cwd, capture_output=True, text=True, timeout=60)
                            if result.returncode != 0:
                                raise RuntimeError(result.stderr or result.stdout or 'VASPKIT failed')

                            x_path = os.path.join(self.cwd, 'X.grd')
                            y_path = os.path.join(self.cwd, 'Y.grd')
                            v_path = os.path.join(self.cwd, 'POTLAVG.grd')
                            if not os.path.isfile(v_path):
                                raise RuntimeError('POTLAVG.grd not found after running VASPKIT')

                            x_data = None
                            if os.path.isfile(x_path):
                                x_data = np.loadtxt(x_path)
                            elif os.path.isfile(y_path):
                                x_data = np.loadtxt(y_path)

                            v_data = np.loadtxt(v_path)

                            # Robustly handle 2-column outputs
                            if v_data.ndim > 1:
                                if x_data is None:
                                    x_data = v_data[:, 0]
                                v_data = v_data[:, -1]
                            if x_data is None:
                                raise RuntimeError('X.grd/Y.grd not found after running VASPKIT')
                            if x_data.ndim > 1:
                                x_data = x_data.ravel()
                            if v_data.ndim > 1:
                                v_data = v_data.ravel()
                            if x_data.shape[0] != v_data.shape[0]:
                                n = min(x_data.shape[0], v_data.shape[0])
                                if n <= 0:
                                    raise RuntimeError('Mismatch between X and POTLAVG grid lengths (empty arrays)')
                                x_data = x_data[:n]
                                v_data = v_data[:n]

                            axis_label = {'ab': 'c', 'ac': 'b', 'bc': 'a'}.get(self.plane_label, 'c')
                            meta = {'axis_label': f'Position along {axis_label} (Å)'}
                            self.result.emit(x_data, v_data, meta)
                        except Exception as e:
                            self.error.emit(str(e))

                try:
                    if hasattr(self.plot_button, 'widget'):
                        self.plot_button.widget.setEnabled(False)
                except Exception:
                    pass
                QApplication.setOverrideCursor(Qt.WaitCursor)

                self._lavg_worker = LinearAvgWorker(loc, plane_input, rep_a, rep_b, plane, loc_dir)

                def on_lavg_error(msg):
                    QApplication.restoreOverrideCursor()
                    try:
                        if hasattr(self.plot_button, 'widget'):
                            self.plot_button.widget.setEnabled(True)
                    except Exception:
                        pass
                    ui.showerror(_('Error'), _('Error reading linear-average potential:\n') + str(msg))

                def on_lavg_result(x_data, v_data, meta):
                    QApplication.restoreOverrideCursor()
                    try:
                        if hasattr(self.plot_button, 'widget'):
                            self.plot_button.widget.setEnabled(True)
                    except Exception:
                        pass
                    try:
                        self._cached_lavg_loc = loc
                        self._cached_lavg_plane = plane
                        self._cached_lavg_rep_a = rep_a
                        self._cached_lavg_rep_b = rep_b
                        self._cached_lavg_x = x_data
                        self._cached_lavg_v = v_data
                        self._cached_lavg_meta = meta
                    except Exception:
                        pass
                    try:
                        self._plot_linear_avg(x_data, v_data, meta)
                    except Exception as e:
                        ui.showerror(_('Error'), _('Error plotting linear-average potential:\n') + str(e))

                def on_lavg_finished():
                    try:
                        if hasattr(self.plot_button, 'widget'):
                            self.plot_button.widget.setEnabled(True)
                    except Exception:
                        pass
                    QApplication.restoreOverrideCursor()
                    try:
                        self._lavg_worker = None
                    except Exception:
                        pass

                self._lavg_worker.error.connect(on_lavg_error)
                self._lavg_worker.result.connect(on_lavg_result)
                self._lavg_worker.finished.connect(on_lavg_finished)
                self._lavg_worker.start()
                return
            except Exception as e:
                try:
                    QApplication.restoreOverrideCursor()
                except Exception:
                    pass
                ui.showerror(_('Error'), _('Error launching linear-average calculation:\n') + str(e))
                return
        elif plot_type == 'Macroscopic-Average Potential':
            try:
                direction = self.axis_combo.value
                axis_map = {'a': '1', 'b': '2', 'c': '3'}
                axis_input = axis_map.get(direction, '3')
            except Exception:
                axis_input = '3'
                direction = 'c'

            try:
                period = float(self.period_entry.value) if hasattr(self, 'period_entry') else 2.0
            except Exception:
                period = 2.0
            try:
                iterations = int(self.iter_entry.value) if hasattr(self, 'iter_entry') else 2
            except Exception:
                iterations = 2

            loc_dir = os.path.dirname(loc) or os.getcwd()

            class MacroAvgWorker(QThread):
                result = pyqtSignal(object, object, object, object)
                error = pyqtSignal(str)

                def __init__(self, path, axis_code, period_val, iter_val, axis_label, cwd):
                    super().__init__()
                    self.path = path
                    self.axis_code = axis_code
                    self.period_val = period_val
                    self.iter_val = iter_val
                    self.axis_label = axis_label
                    self.cwd = cwd

                def run(self):
                    try:
                        cmd = f'(echo 42; sleep 0.5; echo 427; sleep 0.5; echo {self.axis_code}; sleep 0.5; echo {self.period_val}; sleep 0.5; echo {self.iter_val}) | vaspkit'
                        result = subprocess.run(cmd, shell=True, cwd=self.cwd, capture_output=True, text=True, timeout=60)
                        if result.returncode != 0:
                            raise RuntimeError(result.stderr or result.stdout or 'VASPKIT failed')

                        data_path = os.path.join(self.cwd, 'MACROSCOPIC_AVERAGE.dat')
                        if not os.path.isfile(data_path):
                            raise RuntimeError('MACROSCOPIC_AVERAGE.dat not found after running VASPKIT')

                        data = np.loadtxt(data_path, comments='#')
                        if data.ndim == 1:
                            data = data.reshape(-1, data.shape[0])
                        if data.shape[1] < 3:
                            raise RuntimeError('MACROSCOPIC_AVERAGE.dat missing expected columns')
                        z = data[:, 0]
                        v_macro = data[:, 1]
                        v_planar = data[:, 2]
                        if z.ndim > 1:
                            z = z.ravel()
                        if v_macro.ndim > 1:
                            v_macro = v_macro.ravel()
                        if v_planar.ndim > 1:
                            v_planar = v_planar.ravel()
                        n = min(len(z), len(v_macro), len(v_planar))
                        if n <= 0:
                            raise RuntimeError('Empty MACROSCOPIC_AVERAGE.dat content')
                        z = z[:n]
                        v_macro = v_macro[:n]
                        v_planar = v_planar[:n]
                        meta = {'axis_label': f'Position along {self.axis_label} (Å)'}
                        self.result.emit(z, v_macro, v_planar, meta)
                    except Exception as e:
                        self.error.emit(str(e))

            try:
                if hasattr(self.plot_button, 'widget'):
                    self.plot_button.widget.setEnabled(False)
            except Exception:
                pass
            QApplication.setOverrideCursor(Qt.WaitCursor)

            self._macro_worker = MacroAvgWorker(loc, axis_input, period, iterations, direction, loc_dir)

            def on_macro_error(msg):
                QApplication.restoreOverrideCursor()
                try:
                    if hasattr(self.plot_button, 'widget'):
                        self.plot_button.widget.setEnabled(True)
                except Exception:
                    pass
                ui.showerror(_('Error'), _('Error reading macroscopic-average potential:\n') + str(msg))

            def on_macro_result(z, v_macro, v_planar, meta):
                QApplication.restoreOverrideCursor()
                try:
                    if hasattr(self.plot_button, 'widget'):
                        self.plot_button.widget.setEnabled(True)
                except Exception:
                    pass
                try:
                    self._cached_macro_loc = loc
                    self._cached_macro_axis = direction
                    self._cached_macro_period = period
                    self._cached_macro_iter = iterations
                    self._cached_macro_z = z
                    self._cached_macro_vmacro = v_macro
                    self._cached_macro_vplanar = v_planar
                    self._cached_macro_meta = meta
                except Exception:
                    pass
                try:
                    self._plot_macro_avg(z, v_macro, v_planar, meta)
                except Exception as e:
                    ui.showerror(_('Error'), _('Error plotting macroscopic-average potential:\n') + str(e))

            def on_macro_finished():
                try:
                    if hasattr(self.plot_button, 'widget'):
                        self.plot_button.widget.setEnabled(True)
                except Exception:
                    pass
                QApplication.restoreOverrideCursor()
                try:
                    self._macro_worker = None
                except Exception:
                    pass

            self._macro_worker.error.connect(on_macro_error)
            self._macro_worker.result.connect(on_macro_result)
            self._macro_worker.finished.connect(on_macro_finished)
            self._macro_worker.start()
            return
        else:
            ui.showinfo(_('Info'), _('Plot type not implemented yet.'))

    def close(self):
        # If a LOCPOT worker is running, attempt to stop it cleanly before closing
        try:
            worker = getattr(self, '_locpot_worker', None)
            if worker is not None and worker.isRunning():
                try:
                    worker.quit()
                    # Wait briefly for clean shutdown
                    worker.wait(2000)
                except Exception:
                    pass
                # If still running, force terminate (last resort)
                if worker.isRunning():
                    try:
                        worker.terminate()
                        worker.wait(2000)
                    except Exception:
                        pass
        except Exception:
            pass
        self.win.close()

    def _on_setting_changed(self, *args):
        """Called when a plot setting changes; schedule auto-plot if preview enabled."""
        if getattr(self, 'auto_preview_check', None) and self.auto_preview_check.var.get():
            self._schedule_auto_plot()

    def _on_text_changed(self, *args):
        """Called when text entry changes; debounce with timer to avoid rapid updates."""
        if not (getattr(self, 'auto_preview_check', None) and self.auto_preview_check.var.get()):
            return
        # Debounce: restart timer on each keystroke
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
        QTimer.singleShot(200, self._do_auto_plot)

    def _do_auto_plot(self):
        """Execute the auto-plot."""
        self._update_pending = False
        if not (getattr(self, 'auto_preview_check', None) and self.auto_preview_check.var.get()):
            return

        # Skip if worker running
        worker = getattr(self, '_locpot_worker', None)
        lavg_worker = getattr(self, '_lavg_worker', None)
        macro_worker = getattr(self, '_macro_worker', None)
        if (worker is not None and worker.isRunning()) or (lavg_worker is not None and lavg_worker.isRunning()) or (macro_worker is not None and macro_worker.isRunning()):
            return

        try:
            plot_type = self.type_combo.value
        except Exception:
            return

        if plot_type == 'Planar-Average Potential':
            cur_loc = self.loc_entry.value.strip()
            cur_dir = self.axis_combo.value
            if (self._cached_loc == cur_loc and self._cached_direction == cur_dir
                    and self._cached_z is not None):
                try:
                    self._plot_planar_avg(self._cached_z, self._cached_vz, self._cached_meta, auto_refresh=True)
                except Exception:
                    pass
            else:
                try:
                    self.plot()
                except Exception:
                    pass
        elif plot_type == 'Linear-Average Potential':
            cur_loc = self.loc_entry.value.strip()
            cur_plane = getattr(self, 'plane_combo', None).value if hasattr(self, 'plane_combo') else 'ab'
            try:
                cur_rep_a = int(getattr(self, 'rep_a_entry', None).value) if hasattr(self, 'rep_a_entry') else 1
            except Exception:
                cur_rep_a = 1
            try:
                cur_rep_b = int(getattr(self, 'rep_b_entry', None).value) if hasattr(self, 'rep_b_entry') else 1
            except Exception:
                cur_rep_b = 1

            if (self._cached_lavg_loc == cur_loc and self._cached_lavg_plane == cur_plane
                    and self._cached_lavg_rep_a == cur_rep_a and self._cached_lavg_rep_b == cur_rep_b
                    and self._cached_lavg_x is not None):
                try:
                    self._plot_linear_avg(self._cached_lavg_x, self._cached_lavg_v, self._cached_lavg_meta, auto_refresh=True)
                except Exception:
                    pass
            else:
                try:
                    self.plot()
                except Exception:
                    pass
        elif plot_type == 'Macroscopic-Average Potential':
            cur_loc = self.loc_entry.value.strip()
            try:
                cur_axis = self.axis_combo.value
            except Exception:
                cur_axis = 'c'
            try:
                cur_period = float(getattr(self, 'period_entry', None).value) if hasattr(self, 'period_entry') else 2.0
            except Exception:
                cur_period = 2.0
            try:
                cur_iter = int(getattr(self, 'iter_entry', None).value) if hasattr(self, 'iter_entry') else 2
            except Exception:
                cur_iter = 2

            if (self._cached_macro_loc == cur_loc and self._cached_macro_axis == cur_axis
                    and self._cached_macro_period == cur_period and self._cached_macro_iter == cur_iter
                    and self._cached_macro_z is not None):
                try:
                    self._plot_macro_avg(self._cached_macro_z, self._cached_macro_vmacro, self._cached_macro_vplanar, self._cached_macro_meta, auto_refresh=True)
                except Exception:
                    pass
            else:
                try:
                    self.plot()
                except Exception:
                    pass
        else:
            return

    def _connect_auto_preview_handlers(self):
        """Connect widget signals to _on_setting_changed for event-driven updates."""
        if self._preview_handlers_connected:
            return
        try:
            # Helper: connect checkbox
            def connect_checkbox(chk):
                if hasattr(chk, 'widget') and chk.widget:
                    try:
                        chk.widget.stateChanged.connect(self._on_setting_changed)
                    except Exception:
                        pass

            # Helper: connect spinbox
            def connect_spinbox(sp):
                if hasattr(sp, 'widget') and sp.widget:
                    try:
                        sp.widget.valueChanged.connect(self._on_setting_changed)
                    except Exception:
                        pass

            def connect_combo(combo):
                if hasattr(combo, 'widget') and combo.widget:
                    try:
                        combo.widget.currentIndexChanged.connect(self._on_setting_changed)
                    except Exception:
                        pass

            # Helper: connect entry (use textEdited for debounced text changes)
            def connect_entry(ent):
                if hasattr(ent, 'widget') and ent.widget:
                    try:
                        # Use textEdited (user input only) with debouncing for text fields
                        ent.widget.textEdited.connect(self._on_text_changed)
                    except Exception:
                        pass

            # Connect common widgets
            try:
                connect_entry(self.loc_entry)
            except Exception:
                pass
            try:
                connect_combo(self.axis_combo)
            except Exception:
                pass
            try:
                connect_entry(self.title_entry)
            except Exception:
                pass
            try:
                connect_entry(self.xlabel_entry)
            except Exception:
                pass
            try:
                connect_entry(self.ylabel_entry)
            except Exception:
                pass
            for ent_name in ('rep_a_entry', 'rep_b_entry', 'period_entry', 'iter_entry'):
                try:
                    connect_entry(getattr(self, ent_name))
                except Exception:
                    pass
            try:
                connect_combo(self.plane_combo)
            except Exception:
                pass
            for sp in ('title_fontsize', 'xlabel_fontsize', 'ylabel_fontsize', 'xlim_min', 'xlim_max', 'ylim_min', 'ylim_max'):
                try:
                    connect_spinbox(getattr(self, sp))
                except Exception:
                    pass
            for chk in ('show_vac_check', 'show_fermi_check', 'show_wf_check', 'fill_check', 'grid_check'):
                try:
                    connect_checkbox(getattr(self, chk))
                except Exception:
                    pass

            self._preview_handlers_connected = True
        except Exception:
            pass

    def _disconnect_auto_preview_handlers(self):
        """Disconnect event-driven handlers (best-effort)."""
        if not self._preview_handlers_connected:
            return
        try:
            def disconnect_if_possible(sig, slot):
                try:
                    sig.disconnect(slot)
                except Exception:
                    pass

            try:
                disconnect_if_possible(self.loc_entry.widget.textEdited, self._on_text_changed)
            except Exception:
                pass
            try:
                disconnect_if_possible(self.title_entry.widget.textEdited, self._on_text_changed)
            except Exception:
                pass
            try:
                disconnect_if_possible(self.xlabel_entry.widget.textEdited, self._on_text_changed)
            except Exception:
                pass
            try:
                disconnect_if_possible(self.ylabel_entry.widget.textEdited, self._on_text_changed)
            except Exception:
                pass
            try:
                disconnect_if_possible(self.axis_combo.widget.currentIndexChanged, self._on_setting_changed)
            except Exception:
                pass
            try:
                disconnect_if_possible(self.plane_combo.widget.currentIndexChanged, self._on_setting_changed)
            except Exception:
                pass
            for ent_name in ('rep_a_entry', 'rep_b_entry', 'period_entry', 'iter_entry'):
                try:
                    ent = getattr(self, ent_name)
                    disconnect_if_possible(ent.widget.textEdited, self._on_text_changed)
                except Exception:
                    pass
            for sp in ('title_fontsize', 'xlabel_fontsize', 'ylabel_fontsize', 'xlim_min', 'xlim_max', 'ylim_min', 'ylim_max'):
                try:
                    disconnect_if_possible(getattr(self, sp).widget.valueChanged, self._on_setting_changed)
                except Exception:
                    pass
            for chk in ('show_vac_check', 'show_fermi_check', 'show_wf_check', 'fill_check', 'grid_check'):
                try:
                    disconnect_if_possible(getattr(self, chk).widget.stateChanged, self._on_setting_changed)
                except Exception:
                    pass

            self._preview_handlers_connected = False
        except Exception:
            pass

    def _plot_planar_avg(self, z, vz, meta, auto_refresh=False):
        """Plot planar average on the main thread. Handles downsampling and UI options."""
        # Get current loc and direction (may have changed while worker ran)
        loc = self.loc_entry.value.strip()
        direction = self.axis_combo.value

        # Read customization options (if present)
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

        # Downsample large arrays for interactive plotting
        try:
            max_points = 5000
            n = len(z)
            step = max(1, n // max_points)
            if step > 1:
                z_plot = z[::step]
                vz_plot = vz[::step]
            else:
                z_plot = z
                vz_plot = vz
        except Exception:
            z_plot = z
            vz_plot = vz

        # Compute vacuum/work function via vaspkit if requested; best-effort
        vacuum_level = None
        work_function = None
        # Only run external tools when this is an explicit user Plot (not auto-refresh)
        if not auto_refresh:
            try:
                axis_map = {'a': '1', 'b': '2', 'c': '3'}
                axis_input = axis_map.get(direction, '3')
                loc_dir = os.path.dirname(loc) or os.getcwd()
                cmd = f'(echo 42; sleep 0.5; echo 426; sleep 0.5; echo {axis_input}) | vaspkit'
                result = subprocess.run(cmd, shell=True, cwd=loc_dir, capture_output=True, text=True, timeout=30)
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
                if vacuum_level is not None and hasattr(self, 'vac_value_entry'):
                    self.vac_value_entry.value = f'{vacuum_level:.4f} eV'
                elif hasattr(self, 'vac_value_entry'):
                    self.vac_value_entry.value = 'N/A'
                if work_function is not None and hasattr(self, 'wf_value_entry'):
                    self.wf_value_entry.value = f'{work_function:.4f} eV'
                elif hasattr(self, 'wf_value_entry'):
                    self.wf_value_entry.value = 'N/A'
                # cache
                self._cached_vacuum = vacuum_level
                self._cached_work = work_function
            except Exception:
                if hasattr(self, 'vac_value_entry'):
                    self.vac_value_entry.value = 'N/A'
                if hasattr(self, 'wf_value_entry'):
                    self.wf_value_entry.value = 'N/A'
                self._cached_vacuum = None
                self._cached_work = None
        else:
            # For auto-refresh don't invoke vaspkit; try to use cached values
            vacuum_level = self._cached_vacuum
            work_function = self._cached_work
            if hasattr(self, 'vac_value_entry'):
                self.vac_value_entry.value = f'{vacuum_level:.4f} eV' if vacuum_level is not None else 'N/A'
            if hasattr(self, 'wf_value_entry'):
                self.wf_value_entry.value = f'{work_function:.4f} eV' if work_function is not None else 'N/A'

        # Read fermi from OUTCAR
        fermi_level = None
        # Only read OUTCAR when user explicitly requested Plot; skip on auto-refresh
        if not auto_refresh:
            try:
                loc_dir = os.path.dirname(loc) or os.getcwd()
                outcar_path = os.path.join(loc_dir, 'OUTCAR')
                fermi_level = parse_outcar_fermi(outcar_path)
                if fermi_level is not None and hasattr(self, 'fermi_value_entry'):
                    self.fermi_value_entry.value = f'{fermi_level:.4f} eV'
                elif hasattr(self, 'fermi_value_entry'):
                    self.fermi_value_entry.value = 'N/A'
                self._cached_fermi = fermi_level
            except Exception:
                if hasattr(self, 'fermi_value_entry'):
                    self.fermi_value_entry.value = 'N/A'
                self._cached_fermi = None
        else:
            fermi_level = self._cached_fermi
            if hasattr(self, 'fermi_value_entry'):
                self.fermi_value_entry.value = f'{fermi_level:.4f} eV' if fermi_level is not None else 'N/A'

        # Plot: reuse existing figure/axes for fast live preview
        # Preserve focus to prevent input interruption
        focused_widget = None
        if auto_refresh:
            try:
                focused_widget = QApplication.focusWidget()
            except Exception:
                pass
        
        try:
            if auto_refresh and self.plot_figure is not None and plt.fignum_exists(self.plot_figure.number):
                fig = self.plot_figure
                ax = fig.gca()
                # Update existing Line2D for fast refresh
                try:
                    if self._main_line is not None:
                        self._main_line.set_data(z_plot, vz_plot)
                    else:
                        self._main_line, = ax.plot(z_plot, vz_plot)
                except Exception:
                    ax.clear()
                    self._main_line, = ax.plot(z_plot, vz_plot)
                    self._fill_collection = None
                    self._wf_annotation = None
                
                # Handle fill under curve for auto-refresh
                if fill:
                    if self._fill_collection is None:
                        # Match the fill color to the main line color
                        line_color = self._main_line.get_color() if self._main_line else None
                        self._fill_collection = ax.fill_between(z_plot, vz_plot, alpha=0.3, color=line_color)
                    else:
                        # Update existing fill - preserve color
                        try:
                            fill_color = self._fill_collection.get_facecolor()[0][:3]  # Get RGB, ignore alpha
                            self._fill_collection.remove()
                            self._fill_collection = ax.fill_between(z_plot, vz_plot, alpha=0.3, color=fill_color)
                        except Exception:
                            # Fallback: use main line color
                            line_color = self._main_line.get_color() if self._main_line else None
                            self._fill_collection = ax.fill_between(z_plot, vz_plot, alpha=0.3, color=line_color)
                else:
                    # Remove fill if unchecked
                    if self._fill_collection is not None:
                        try:
                            self._fill_collection.remove()
                        except Exception:
                            pass
                        self._fill_collection = None
            else:
                fig = plt.figure()
                ax = plt.gca()
                self.plot_figure = fig
                self._main_line, = ax.plot(z_plot, vz_plot)
                if fill:
                    # Match the fill color to the main line color
                    line_color = self._main_line.get_color()
                    self._fill_collection = ax.fill_between(z_plot, vz_plot, alpha=0.3, color=line_color)
            if xlabel is not None:
                ax.set_xlabel(xlabel, fontsize=xlabel_fs)
            if ylabel is not None:
                ax.set_ylabel(ylabel, fontsize=ylabel_fs)
            if title is not None:
                ax.set_title(title, fontsize=title_fs)
            if show_grid:
                ax.grid(True, alpha=0.3)
            # Update or create marker lines for vacuum/fermi only when requested
            try:
                if hasattr(self, 'show_vac_check') and self.show_vac_check.var.get() and vacuum_level is not None:
                    if self._vac_line is None:
                        self._vac_line = ax.axhline(vacuum_level, color='orange', linestyle='--', label=_('Vacuum level'))
                    else:
                        try:
                            self._vac_line.set_ydata([vacuum_level, vacuum_level])
                        except Exception:
                            # recreate if needed
                            self._vac_line.remove()
                            self._vac_line = ax.axhline(vacuum_level, color='orange', linestyle='--', label=_('Vacuum level'))
                else:
                    if self._vac_line is not None:
                        try:
                            self._vac_line.remove()
                        except Exception:
                            pass
                        self._vac_line = None
            except Exception:
                pass

            try:
                if hasattr(self, 'show_fermi_check') and self.show_fermi_check.var.get() and fermi_level is not None:
                    if self._fermi_line is None:
                        self._fermi_line = ax.axhline(fermi_level, color='red', linestyle=':', label=_('Fermi level'))
                    else:
                        try:
                            self._fermi_line.set_ydata([fermi_level, fermi_level])
                        except Exception:
                            self._fermi_line.remove()
                            self._fermi_line = ax.axhline(fermi_level, color='red', linestyle=':', label=_('Fermi level'))
                else:
                    if self._fermi_line is not None:
                        try:
                            self._fermi_line.remove()
                        except Exception:
                            pass
                        self._fermi_line = None
            except Exception:
                pass
            if xlim is not None:
                ax.set_xlim(xlim)
            if ylim is not None:
                ax.set_ylim(ylim)
            
            # Update spinboxes with actual plot limits
            try:
                actual_xlim = ax.get_xlim()
                actual_ylim = ax.get_ylim()
                if hasattr(self, 'xlim_min') and hasattr(self, 'xlim_max'):
                    self.xlim_min.value = round(actual_xlim[0], 2)
                    self.xlim_max.value = round(actual_xlim[1], 2)
                if hasattr(self, 'ylim_min') and hasattr(self, 'ylim_max'):
                    self.ylim_min.value = round(actual_ylim[0], 2)
                    self.ylim_max.value = round(actual_ylim[1], 2)
            except Exception:
                pass
            
            # Work function annotation
            if hasattr(self, 'show_wf_check') and self.show_wf_check.var.get() and work_function is not None:
                # Remove old annotation if it exists
                if self._wf_annotation is not None:
                    try:
                        self._wf_annotation.remove()
                    except Exception:
                        pass
                self._wf_annotation = ax.text(0.02, 0.98, f'Work Function: {work_function:.4f} eV', 
                                              transform=ax.transAxes, verticalalignment='top', 
                                              bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            else:
                # Remove annotation if unchecked
                if self._wf_annotation is not None:
                    try:
                        self._wf_annotation.remove()
                    except Exception:
                        pass
                    self._wf_annotation = None
            # Legend
            show_legend = False
            if hasattr(self, 'show_vac_check') and self.show_vac_check.var.get() and vacuum_level is not None:
                show_legend = True
            if hasattr(self, 'show_fermi_check') and self.show_fermi_check.var.get() and fermi_level is not None:
                show_legend = True
            if show_legend:
                ax.legend()
            else:
                # Remove legend if no markers are shown
                legend = ax.get_legend()
                if legend is not None:
                    legend.remove()

            # Draw / show
            try:
                if auto_refresh:
                    # For live preview: only redraw canvas without activating window
                    fig.canvas.draw_idle()
                else:
                    # For explicit Plot: show the figure window
                    fig.canvas.draw_idle()
                    try:
                        fig.show()
                    except Exception:
                        pass
                    try:
                        plt.pause(0.001)
                    except Exception:
                        pass
            except Exception:
                if not auto_refresh:
                    plt.show()
            # Restore focus after plot update to prevent input interruption
            if auto_refresh and focused_widget is not None:
                try:
                    if focused_widget.isVisible():
                        focused_widget.setFocus(Qt.OtherFocusReason)
                except Exception:
                    pass
        except Exception:
            # Fallback to simple plotting on error (only for explicit plot)
            if not auto_refresh:
                plt.figure()
                if fill:
                    plt.fill_between(z_plot, vz_plot, alpha=0.3)
                plt.plot(z_plot, vz_plot)
                plt.show()

    def _plot_linear_avg(self, x_data, v_data, meta, auto_refresh=False):
        """Plot linear-average potential data."""
        title = self.title_entry.value.strip() if hasattr(self, 'show_title_check') and self.show_title_check.var.get() else None
        xlabel = meta.get('axis_label', _('Position (Å)')) if isinstance(meta, dict) else _('Position (Å)')
        ylabel = self.ylabel_entry.value.strip() if hasattr(self, 'show_ylabel_check') and self.show_ylabel_check.var.get() else _('Linear-averaged electrostatic potential (eV)')
        if hasattr(self, 'show_xlabel_check') and self.show_xlabel_check.var.get() and hasattr(self, 'xlabel_entry'):
            try:
                xlabel = self.xlabel_entry.value.strip()
            except Exception:
                pass
        title_fs = getattr(self, 'title_fontsize', None).value if hasattr(self, 'title_fontsize') else 14
        xlabel_fs = getattr(self, 'xlabel_fontsize', None).value if hasattr(self, 'xlabel_fontsize') else 12
        ylabel_fs = getattr(self, 'ylabel_fontsize', None).value if hasattr(self, 'ylabel_fontsize') else 12
        show_grid = getattr(self, 'grid_check', None).var.get() if hasattr(self, 'grid_check') else True

        # Downsample for interactive plotting
        try:
            max_points = 5000
            n = len(x_data)
            step = max(1, n // max_points)
            x_plot = x_data[::step]
            v_plot = v_data[::step]
        except Exception:
            x_plot = x_data
            v_plot = v_data

        try:
            if self.plot_figure is None or not plt.fignum_exists(self.plot_figure.number):
                fig, ax = plt.subplots()
                self.plot_figure = fig
                self.plot_axes = ax
            else:
                fig = self.plot_figure
                ax = self.plot_axes
                ax.clear()

            ax.plot(x_plot, v_plot, label=_('Linear average'))
            ax.set_xlabel(xlabel, fontsize=xlabel_fs)
            ax.set_ylabel(ylabel, fontsize=ylabel_fs)
            if title:
                ax.set_title(title, fontsize=title_fs)
            if show_grid:
                ax.grid(True)
            # Optional limits
            try:
                if hasattr(self, 'xlim_min') and hasattr(self, 'xlim_max'):
                    xmin = self.xlim_min.value
                    xmax = self.xlim_max.value
                    if xmin < xmax:
                        ax.set_xlim(xmin, xmax)
                if hasattr(self, 'ylim_min') and hasattr(self, 'ylim_max'):
                    ymin = self.ylim_min.value
                    ymax = self.ylim_max.value
                    if ymin < ymax:
                        ax.set_ylim(ymin, ymax)
            except Exception:
                pass
            ax.legend()

            try:
                if auto_refresh:
                    fig.canvas.draw_idle()
                else:
                    fig.canvas.draw_idle()
                    fig.show()
                    plt.pause(0.001)
            except Exception:
                if not auto_refresh:
                    plt.show()
        except Exception:
            if not auto_refresh:
                plt.figure()
                plt.plot(x_plot, v_plot)
                plt.xlabel(xlabel)
                plt.ylabel(ylabel)
                if title:
                    plt.title(title)
                plt.show()

    def _plot_macro_avg(self, z, v_macro, v_planar, meta, auto_refresh=False):
        """Plot macroscopic and planar averages together."""
        title = self.title_entry.value.strip() if hasattr(self, 'show_title_check') and self.show_title_check.var.get() else None
        xlabel = meta.get('axis_label', _('Position (Å)')) if isinstance(meta, dict) else _('Position (Å)')
        ylabel = self.ylabel_entry.value.strip() if hasattr(self, 'show_ylabel_check') and self.show_ylabel_check.var.get() else _('Potential (eV)')
        if hasattr(self, 'show_xlabel_check') and self.show_xlabel_check.var.get() and hasattr(self, 'xlabel_entry'):
            try:
                xlabel = self.xlabel_entry.value.strip()
            except Exception:
                pass
        title_fs = getattr(self, 'title_fontsize', None).value if hasattr(self, 'title_fontsize') else 14
        xlabel_fs = getattr(self, 'xlabel_fontsize', None).value if hasattr(self, 'xlabel_fontsize') else 12
        ylabel_fs = getattr(self, 'ylabel_fontsize', None).value if hasattr(self, 'ylabel_fontsize') else 12
        show_grid = getattr(self, 'grid_check', None).var.get() if hasattr(self, 'grid_check') else True

        try:
            max_points = 5000
            n = len(z)
            step = max(1, n // max_points)
            z_plot = z[::step]
            v_macro_plot = v_macro[::step]
            v_planar_plot = v_planar[::step]
        except Exception:
            z_plot = z
            v_macro_plot = v_macro
            v_planar_plot = v_planar

        try:
            if self.plot_figure is None or not plt.fignum_exists(self.plot_figure.number):
                fig, ax = plt.subplots()
                self.plot_figure = fig
                self.plot_axes = ax
            else:
                fig = self.plot_figure
                ax = self.plot_axes
                ax.clear()

            ax.plot(z_plot, v_planar_plot, label=_('Planar average'), linestyle='--')
            ax.plot(z_plot, v_macro_plot, label=_('Macroscopic average'))
            ax.set_xlabel(xlabel, fontsize=xlabel_fs)
            ax.set_ylabel(ylabel, fontsize=ylabel_fs)
            if title:
                ax.set_title(title, fontsize=title_fs)
            if show_grid:
                ax.grid(True)
            try:
                if hasattr(self, 'xlim_min') and hasattr(self, 'xlim_max'):
                    xmin = self.xlim_min.value
                    xmax = self.xlim_max.value
                    if xmin < xmax:
                        ax.set_xlim(xmin, xmax)
                if hasattr(self, 'ylim_min') and hasattr(self, 'ylim_max'):
                    ymin = self.ylim_min.value
                    ymax = self.ylim_max.value
                    if ymin < ymax:
                        ax.set_ylim(ymin, ymax)
            except Exception:
                pass
            ax.legend()

            try:
                if auto_refresh:
                    fig.canvas.draw_idle()
                else:
                    fig.canvas.draw_idle()
                    fig.show()
                    plt.pause(0.001)
            except Exception:
                if not auto_refresh:
                    plt.show()
        except Exception:
            if not auto_refresh:
                plt.figure()
                plt.plot(z_plot, v_macro_plot, label=_('Macroscopic average'))
                plt.plot(z_plot, v_planar_plot, label=_('Planar average'), linestyle='--')
                plt.xlabel(xlabel)
                plt.ylabel(ylabel)
                if title:
                    plt.title(title)
                plt.legend()
                plt.show()


def potential_plot_window(gui):
    PotentialPlotter(gui)
