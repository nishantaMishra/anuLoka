# fmt: off

"""colors_qt.py - Qt version of color selection dialog."""
import os
import numpy as np

import ase.gui.ui_qt as ui
from ase.gui.i18n import _
from ase.gui.utils import get_magmoms
from ase.data import chemical_symbols

# Load color schemes from YAML file
def load_color_schemes():
    """Load element color schemes from YAML file."""
    import yaml
    yaml_path = os.path.join(os.path.dirname(__file__), '..', 'DOS', 'ElementColorSchemes.yaml')
    schemes = {}
    if os.path.exists(yaml_path):
        with open(yaml_path, 'r') as f:
            schemes = yaml.safe_load(f)
    return schemes, yaml_path


def save_color_schemes(schemes, yaml_path):
    """Save color schemes back to YAML file."""
    import yaml
    with open(yaml_path, 'w') as f:
        yaml.dump(schemes, f, default_flow_style=None, allow_unicode=True, sort_keys=False)


def scheme_to_colors_dict(scheme_data):
    """Convert a color scheme dict to the format used by view (atomic_number -> hex color)."""
    colors = {}
    for symbol, rgb in scheme_data.items():
        if symbol in chemical_symbols:
            Z = chemical_symbols.index(symbol)
            colors[Z] = '#{:02X}{:02X}{:02X}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))
    return colors


class ColorWindow:
    """A window for selecting how to color the atoms."""

    def __init__(self, gui):
        self.color_schemes, self.yaml_path = load_color_schemes()
        # Store current scheme in gui object so it persists across dialog reopenings
        if not hasattr(gui, '_color_scheme'):
            gui._color_scheme = 'Jmol'
        self.reset(gui)

    def reset(self, gui):
        """create a new color window"""
        self.win = ui.Window(_('Colors'))
        self.gui = gui
        self.win.add(ui.Label(_('Choose how the atoms are colored:')))
        
        # Color scheme selector for atomic number coloring
        scheme_names = list(self.color_schemes.keys())
        # Filter out 'Extras' as it's for special element types
        scheme_names = [s for s in scheme_names if s != 'Extras']
        
        # Store scheme widgets to show/hide based on colormode
        self._scheme_widgets = []
        
        if scheme_names:
            scheme_label = ui.Label(_('Color scheme:'))
            self.win.add(scheme_label)
            self._scheme_widgets.append(scheme_label)
            
            self.scheme_combo = ui.ComboBox(scheme_names, scheme_names, self.change_scheme)
            if gui._color_scheme in scheme_names:
                self.scheme_combo.value = gui._color_scheme
            self.win.add(self.scheme_combo)
            self._scheme_widgets.append(self.scheme_combo)
            
            # Add customize button for User scheme
            self.customize_btn = ui.Button(_('Customize User Colors...'), self.open_customize_dialog)
            self.win.add(self.customize_btn)
            self._scheme_widgets.append(self.customize_btn)
        
        self.win.add(ui.Label(''))  # Spacer
        self.win.add(ui.Label(_('Color by property:')))
        
        values = ['jmol', 'tag', 'force', 'velocity',
                  'initial charge', 'magmom', 'neighbors']
        labels = [_('By atomic number (use scheme above)'),
                  _('By tag'),
                  _('By force'),
                  _('By velocity'),
                  _('By initial charge'),
                  _('By magnetic moment'),
                  _('By number of neighbors'), ]

        haveit = ['numbers', 'positions', 'forces', 'momenta',
                  'initial_charges', 'initial_magmoms']
        for key in self.gui.atoms.arrays:
            if key not in haveit:
                values.append(key)
                labels.append(f'By user-defined "{key}"')

        self.radio = ui.RadioButtons(labels, values, self.toggle,
                                     vertical=True)
        self.radio.value = gui.colormode
        self.win.add(self.radio)
        self.activate()
        self.label = ui.Label()
        self.win.add(self.label)

        if hasattr(self, 'mnmx'):
            self.win.add(self.cmaps)
            self.win.add(self.mnmx)
        
        # Update scheme widget visibility based on current mode
        self._update_scheme_visibility(gui.colormode)
        
        # Add separator and default settings section
        self.win.add(ui.Label(''))  # Spacer
        self.win.add(ui.Label('─' * 30))  # Visual separator
        
        # Show current default
        default_scheme = self.gui.config.get('default_color_scheme', 'Jmol')
        default_mode = self.gui.config.get('default_colormode', 'jmol')
        mode_labels = {
            'jmol': 'By atomic number',
            'tag': 'By tag',
            'force': 'By force',
            'velocity': 'By velocity',
            'initial charge': 'By initial charge',
            'magmom': 'By magnetic moment',
            'neighbors': 'By number of neighbors'
        }
        default_mode_label = mode_labels.get(default_mode, default_mode)
        
        if default_mode == 'jmol':
            default_text = f'Default: {default_scheme} ({default_mode_label})'
        else:
            default_text = f'Default: {default_mode_label}'
        
        self.default_label = ui.Label(default_text)
        self.win.add(self.default_label)
        self.win.add(ui.Button(_('Set Current as Default'), self.set_as_default))

    def change_mnmx(self, mn=None, mx=None):
        """change min and/or max values for colormap"""
        if mn:
            self.mnmx[1].value = mn
        if mx:
            self.mnmx[3].value = mx
        mn, mx = self.mnmx[1].value, self.mnmx[3].value
        colorscale, _, _ = self.gui.colormode_data
        self.gui.colormode_data = colorscale, mn, mx
        self.gui.draw()

    def _update_scheme_visibility(self, colormode):
        """Show/hide color scheme widgets based on colormode."""
        show = (colormode == 'jmol')
        for widget in self._scheme_widgets:
            if hasattr(widget, 'widget') and widget.widget is not None:
                widget.widget.setVisible(show)

    def activate(self):
        images = self.gui.images
        atoms = self.gui.atoms
        radio = self.radio
        radio['tag'].active = atoms.has('tags')

        # XXX not sure how to deal with some images having forces,
        # and other images not.  Same goes for below quantities
        F = images.get_forces(atoms)
        radio['force'].active = F is not None
        radio['velocity'].active = atoms.has('momenta')
        radio['initial charge'].active = atoms.has('initial_charges')
        radio['magmom'].active = get_magmoms(atoms).any()
        radio['neighbors'].active = True

    def toggle(self, value):
        self.gui.colormode = value
        
        # Update scheme widget visibility
        self._update_scheme_visibility(value)
        
        if value == 'jmol' or value == 'neighbors':
            if hasattr(self, 'mnmx'):
                "delete the min max fields by creating a new window"
                del self.mnmx
                del self.cmaps
                self.win.close()
                self.reset(self.gui)
            text = ''
        else:
            scalars = np.ma.array([self.gui.get_color_scalars(i)
                                   for i in range(len(self.gui.images))])
            mn = np.min(scalars)
            mx = np.max(scalars)
            self.gui.colormode_data = None, mn, mx

            cmaps = ['default', 'old']
            try:
                import pylab as plt
                cmaps += [m for m in plt.cm.datad if not m.endswith("_r")]
            except ImportError:
                pass
            self.cmaps = [_('cmap:'),
                          ui.ComboBox(cmaps, cmaps, self.update_colormap),
                          _('N:'),
                          ui.SpinBox(26, 0, 100, 1, self.update_colormap)]
            self.update_colormap('default')

            try:
                unit = {'tag': '',
                        'force': 'eV/Ang',
                        'velocity': '(eV/amu)^(1/2)',
                        'charge': '|e|',
                        'initial charge': '|e|',
                        'magmom': 'μB'}[value]
            except KeyError:
                unit = ''
            text = ''

            rng = mx - mn  # XXX what are optimal allowed range and steps ?
            self.mnmx = [_('min:'),
                         ui.SpinBox(mn, mn - 10 * rng, mx + rng, rng / 10.,
                                    self.change_mnmx, width=20),
                         _('max:'),
                         ui.SpinBox(mx, mn - 10 * rng, mx + rng, rng / 10.,
                                    self.change_mnmx, width=20),
                         _(unit)]
            self.win.close()
            self.reset(self.gui)

        self.label.text = text
        self.radio.value = value
        self.gui.draw()
        return text  # for testing

    def notify_atoms_changed(self):
        "Called by gui object when the atoms have changed."
        self.activate()
        mode = self.gui.colormode
        if not self.radio[mode].active:
            mode = 'jmol'
        self.toggle(mode)

    def set_as_default(self):
        """Set current color scheme and mode as default."""
        import os
        
        # Get current settings
        current_mode = self.gui.colormode
        current_scheme = getattr(self.gui, '_color_scheme', 'Jmol')
        
        # Update config
        self.gui.config['default_colormode'] = current_mode
        self.gui.config['default_color_scheme'] = current_scheme
        
        # Save to ~/.ase/gui.py
        config_dir = os.path.expanduser('~/.ase')
        config_file = os.path.join(config_dir, 'gui.py')
        
        # Create directory if it doesn't exist
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        # Read existing config or create new
        existing_lines = []
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                existing_lines = f.readlines()
        
        # Update or add the default settings
        new_lines = []
        found_scheme = False
        found_mode = False
        
        for line in existing_lines:
            if line.strip().startswith("gui_default_settings['default_color_scheme']"):
                new_lines.append(f"gui_default_settings['default_color_scheme'] = '{current_scheme}'\n")
                found_scheme = True
            elif line.strip().startswith("gui_default_settings['default_colormode']"):
                new_lines.append(f"gui_default_settings['default_colormode'] = '{current_mode}'\n")
                found_mode = True
            else:
                new_lines.append(line)
        
        if not found_scheme:
            new_lines.append(f"gui_default_settings['default_color_scheme'] = '{current_scheme}'\n")
        if not found_mode:
            new_lines.append(f"gui_default_settings['default_colormode'] = '{current_mode}'\n")
        
        with open(config_file, 'w') as f:
            f.writelines(new_lines)
        
        # Update the label
        mode_labels = {
            'jmol': 'By atomic number',
            'tag': 'By tag',
            'force': 'By force',
            'velocity': 'By velocity',
            'initial charge': 'By initial charge',
            'magmom': 'By magnetic moment',
            'neighbors': 'By number of neighbors'
        }
        default_mode_label = mode_labels.get(current_mode, current_mode)
        
        if current_mode == 'jmol':
            default_text = f'Default: {current_scheme} ({default_mode_label})'
        else:
            default_text = f'Default: {default_mode_label}'
        
        if hasattr(self, 'default_label') and self.default_label.widget:
            self.default_label.widget.setText(default_text)

    def update_colormap(self, cmap=None, N=26):
        "Called by gui when colormap has changed"
        import matplotlib
        if cmap is None:
            cmap = self.cmaps[1].value
        try:
            N = int(self.cmaps[3].value)
        except AttributeError:
            N = 26
        colorscale, mn, mx = self.gui.colormode_data
        if cmap == 'default':
            colorscale = ['#{0:02X}80{0:02X}'.format(int(red))
                          for red in np.linspace(0, 250, N)]
        elif cmap == 'old':
            colorscale = [f'#{int(red):02X}AA00'
                          for red in np.linspace(0, 230, N)]
        else:
            cmap_obj = matplotlib.colormaps[cmap]
            colorscale = [matplotlib.colors.rgb2hex(c[:3]) for c in
                          cmap_obj(np.linspace(0, 1, N))]
        self.gui.colormode_data = colorscale, mn, mx
        self.gui.draw()

    def change_scheme(self, scheme_name):
        """Change the element color scheme."""
        self.gui._color_scheme = scheme_name
        if scheme_name in self.color_schemes:
            self.gui.colors = scheme_to_colors_dict(self.color_schemes[scheme_name])
            self.gui.draw()

    def open_customize_dialog(self):
        """Open dialog to customize User color scheme with real-time preview."""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                                     QTableWidget, QTableWidgetItem, QPushButton,
                                     QHeaderView, QColorDialog, QMessageBox)
        from PyQt5.QtGui import QColor
        from PyQt5.QtCore import Qt
        
        dialog = QDialog()
        dialog.setWindowTitle(_('Customize User Colors'))
        dialog.setMinimumSize(400, 500)
        layout = QVBoxLayout(dialog)
        
        # Get User scheme or create default
        if 'User' not in self.color_schemes:
            # Copy Jmol as default
            self.color_schemes['User'] = dict(self.color_schemes.get('Jmol', {}))
        
        user_colors = self.color_schemes['User']
        
        # Save original colors for reverting on cancel
        original_gui_colors = self.gui.colors.copy() if hasattr(self.gui, 'colors') else {}
        original_user_scheme = {k: list(v) if isinstance(v, list) else v 
                                for k, v in user_colors.items()}
        colors_saved = [False]  # Use list to allow modification in nested function
        
        # Create table
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels([_('Element'), _('Color'), _('RGB')])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        
        # Populate table with elements
        elements = sorted(user_colors.keys(), key=lambda x: chemical_symbols.index(x) if x in chemical_symbols else 999)
        table.setRowCount(len(elements))
        
        def preview_color(element, rgb):
            """Apply color preview to the view in real-time."""
            if element in chemical_symbols:
                Z = chemical_symbols.index(element)
                self.gui.colors[Z] = '#{:02X}{:02X}{:02X}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))
                self.gui.draw()
        
        def make_color_button(row, element, rgb):
            btn = QPushButton()
            btn.setStyleSheet(f'background-color: rgb({rgb[0]},{rgb[1]},{rgb[2]}); min-width: 60px;')
            btn.setProperty('element', element)
            btn.setProperty('rgb', rgb)
            
            def on_click():
                current_rgb = btn.property('rgb')
                
                # Create color dialog with real-time preview
                color_dlg = QColorDialog(QColor(*current_rgb), dialog)
                color_dlg.setWindowTitle(f'Select color for {element}')
                color_dlg.setOption(QColorDialog.NoButtons, False)
                
                # Connect to currentColorChanged for real-time preview
                def on_color_change(color):
                    if color.isValid():
                        preview_rgb = [color.red(), color.green(), color.blue()]
                        preview_color(element, preview_rgb)
                
                color_dlg.currentColorChanged.connect(on_color_change)
                
                # Show dialog and handle result
                if color_dlg.exec_() == QColorDialog.Accepted:
                    color = color_dlg.currentColor()
                    new_rgb = [color.red(), color.green(), color.blue()]
                    btn.setProperty('rgb', new_rgb)
                    btn.setStyleSheet(f'background-color: rgb({new_rgb[0]},{new_rgb[1]},{new_rgb[2]}); min-width: 60px;')
                    table.item(row, 2).setText(f'{new_rgb[0]}, {new_rgb[1]}, {new_rgb[2]}')
                    # Keep the preview color
                    preview_color(element, new_rgb)
                else:
                    # Revert to previous color on cancel
                    preview_color(element, current_rgb)
            
            btn.clicked.connect(on_click)
            return btn
        
        self._color_buttons = {}
        for row, element in enumerate(elements):
            rgb = user_colors[element]
            if isinstance(rgb, list):
                rgb = list(rgb)
            else:
                rgb = [128, 128, 128]
            
            # Element name
            item = QTableWidgetItem(element)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 0, item)
            
            # Color button
            btn = make_color_button(row, element, rgb)
            table.setCellWidget(row, 1, btn)
            self._color_buttons[element] = btn
            
            # RGB text
            rgb_item = QTableWidgetItem(f'{rgb[0]}, {rgb[1]}, {rgb[2]}')
            rgb_item.setFlags(rgb_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 2, rgb_item)
        
        layout.addWidget(table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton(_('Save'))
        def save_colors():
            for element, btn in self._color_buttons.items():
                rgb = btn.property('rgb')
                self.color_schemes['User'][element] = rgb
            save_color_schemes(self.color_schemes, self.yaml_path)
            colors_saved[0] = True
            # Apply if User scheme is selected
            if hasattr(self, 'scheme_combo') and self.scheme_combo.value == 'User':
                self.change_scheme('User')
            QMessageBox.information(dialog, _('Saved'), _('User colors saved successfully.'))
        
        save_btn.clicked.connect(save_colors)
        btn_layout.addWidget(save_btn)
        
        close_btn = QPushButton(_('Close'))
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec_()
        
        # Revert colors if not saved
        if not colors_saved[0]:
            self.gui.colors = original_gui_colors
            self.color_schemes['User'] = original_user_scheme
            self.gui.draw()
