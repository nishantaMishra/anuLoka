# fmt: off

"""
Qt-based UI module for ASE-GUI.

This module provides a Qt (PyQt5) implementation of the widget abstraction layer
that mirrors the Tkinter-based ui.py API. This allows the ASE-GUI to use Qt
as its backend, enabling features like the matplotlib "Edit axis" button.
"""

import platform
import re
import sys
from collections import namedtuple
from functools import partial

import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QCheckBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QSlider, QRadioButton, QButtonGroup, QComboBox, QTextEdit,
    QFrame, QMenuBar, QMenu, QAction, QActionGroup, QStatusBar, QFileDialog,
    QMessageBox, QTabWidget, QSplitter, QScrollArea, QSizePolicy, QToolTip,
    QGraphicsView, QGraphicsScene
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint, QSize, QMimeData, QUrl
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QKeySequence, QDragEnterEvent,
    QDropEvent, QCursor
)

from ase.gui.i18n import _

__all__ = [
    'error', 'ask_question', 'MainWindow', 'LoadFileDialog', 'SaveFileDialog',
    'ASEGUIWindow', 'Button', 'CheckButton', 'ComboBox', 'Entry', 'Label',
    'Window', 'MenuItem', 'RadioButton', 'RadioButtons', 'Rows', 'Scale',
    'showinfo', 'showwarning', 'showerror', 'SpinBox', 'Text']


# Ensure QApplication exists
_app = None
def get_app():
    global _app
    if _app is None:
        _app = QApplication.instance()
        if _app is None:
            _app = QApplication(sys.argv)
    return _app


def error(title, message=None):
    if message is None:
        message = title
        title = _('Error')
    return showerror(title, message)


def showerror(title, message):
    get_app()
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.exec_()


def showinfo(title, message):
    get_app()
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.exec_()


def showwarning(title, message):
    get_app()
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.exec_()


def ask_question(title, message):
    get_app()
    reply = QMessageBox.question(None, title, message,
                                  QMessageBox.Ok | QMessageBox.Cancel)
    return reply == QMessageBox.Ok


def about(name, version, webpage):
    text = [name,
            '',
            _('Version') + ': ' + version,
            _('Web-page') + ': ' + webpage]
    win = Window(_('About'))
    win.add(Text('\n'.join(text)))


def helpbutton(text):
    return Button(_('Help'), helpwindow, text)


def helpwindow(text):
    win = Window(_('Help'))
    win.add(Text(text))


class BaseWindow:
    """Base class for Qt windows."""
    def __init__(self, title, close=None):
        self._title = title
        self.win.setWindowTitle(title)
        self.close_callback = close
        self.things = []
        self.exists = True
        self._layout = QVBoxLayout()
        
        # Create central widget and set layout
        if hasattr(self.win, 'setCentralWidget'):
            central = QWidget()
            central.setLayout(self._layout)
            self.win.setCentralWidget(central)
        else:
            self.win.setLayout(self._layout)

    def close(self):
        if self.close_callback:
            self.close_callback()
        self.win.close()
        self.exists = False

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, txt):
        self._title = txt
        self.win.setWindowTitle(txt)

    def add(self, stuff, anchor='w'):
        if isinstance(stuff, str):
            stuff = Label(stuff)
        elif isinstance(stuff, list):
            stuff = Row(stuff)
        stuff.pack(self._layout, anchor=anchor)
        self.things.append(stuff)


class Window(BaseWindow):
    """A Qt dialog window."""
    def __init__(self, title, close=None):
        get_app()
        self.win = QDialog()
        super().__init__(title, close)
        self.win.show()


class Widget:
    """Base class for Qt widgets."""
    widget = None
    
    def pack(self, parent, side='top', anchor='center'):
        widget = self.create(parent)
        if isinstance(parent, QVBoxLayout):
            parent.addWidget(widget)
        elif isinstance(parent, QHBoxLayout):
            parent.addWidget(widget)
        elif isinstance(parent, QWidget):
            if parent.layout() is None:
                parent.setLayout(QVBoxLayout())
            parent.layout().addWidget(widget)
        elif hasattr(parent, 'addWidget'):
            parent.addWidget(widget)

    def grid(self, parent):
        widget = self.create(parent)
        if isinstance(parent, QGridLayout):
            parent.addWidget(widget)
        elif isinstance(parent, QWidget):
            if parent.layout() is None:
                parent.setLayout(QGridLayout())
            parent.layout().addWidget(widget)
        elif hasattr(parent, 'layout'):
            layout = parent.layout()
            if layout:
                layout.addWidget(widget)

    def create(self, parent):
        # Get actual parent widget
        if isinstance(parent, (QVBoxLayout, QHBoxLayout, QGridLayout)):
            parent_widget = parent.parentWidget()
        elif isinstance(parent, QWidget):
            parent_widget = parent
        else:
            parent_widget = None
        self.widget = self.creator(parent_widget)
        return self.widget

    @property
    def active(self):
        if self.widget:
            return self.widget.isEnabled()
        return True

    @active.setter
    def active(self, value):
        if self.widget:
            self.widget.setEnabled(bool(value))


class Row(Widget):
    """Horizontal container for widgets."""
    def __init__(self, things):
        self.things = things
        self._frame = None

    def create(self, parent):
        if isinstance(parent, (QVBoxLayout, QHBoxLayout, QGridLayout)):
            parent_widget = parent.parentWidget()
        else:
            parent_widget = parent if isinstance(parent, QWidget) else None
        
        self._frame = QWidget(parent_widget)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        # Reduce default spacing and keep children left-aligned to avoid large gaps
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignLeft)
        self._frame.setLayout(layout)
        
        for thing in self.things:
            if isinstance(thing, str):
                thing = Label(thing)
            thing.pack(layout, 'left')
        
        self.widget = self._frame
        return self._frame

    def __getitem__(self, i):
        return self.things[i]


class Label(Widget):
    """Qt Label widget."""
    def __init__(self, text='', color=None):
        self._text = text
        self._color = color
        self.creator = lambda parent: self._create_label(parent)

    def _create_label(self, parent):
        lbl = QLabel(self._text, parent)
        # Prevent the label from expanding and creating a large gap
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        if self._color:
            lbl.setStyleSheet(f"color: {self._color};")
        return lbl

    @property
    def text(self):
        if self.widget:
            return self.widget.text()
        return self._text

    @text.setter
    def text(self, new):
        self._text = new
        if self.widget:
            self.widget.setText(new)


class Text(Widget):
    """Multi-line text widget with tag support."""
    def __init__(self, text):
        self._raw_text = text
        # Parse tags (sub, sup, c)
        s = re.split('<(.*?)>', text)
        self._parsed = [(s[0], ())]
        i = 1
        tags = []
        while i < len(s):
            tag = s[i]
            if tag[0] != '/':
                tags.append(tag)
            else:
                tags.pop()
            self._parsed.append((s[i + 1], tuple(tags)))
            i += 2

    def create(self, parent):
        if isinstance(parent, (QVBoxLayout, QHBoxLayout, QGridLayout)):
            parent_widget = parent.parentWidget()
        else:
            parent_widget = parent if isinstance(parent, QWidget) else None
        
        self.widget = QTextEdit(parent_widget)
        self.widget.setReadOnly(True)
        
        # Build HTML from parsed text
        html = ""
        for text, tags in self._parsed:
            text_escaped = text.replace('\n', '<br>')
            if 'sub' in tags:
                text_escaped = f"<sub>{text_escaped}</sub>"
            if 'sup' in tags:
                text_escaped = f"<sup>{text_escaped}</sup>"
            if 'c' in tags:
                text_escaped = f"<span style='color: blue;'>{text_escaped}</span>"
            html += text_escaped
        
        self.widget.setHtml(html)
        # Adjust height to content
        line_count = self._raw_text.count('\n') + 1
        self.widget.setFixedHeight(min(line_count * 20 + 20, 300))
        return self.widget


class Button(Widget):
    """Qt Button widget."""
    def __init__(self, text, callback, *args, **kwargs):
        self.callback = partial(callback, *args, **kwargs)
        self._text = text

    def create(self, parent):
        if isinstance(parent, (QVBoxLayout, QHBoxLayout, QGridLayout)):
            parent_widget = parent.parentWidget()
        else:
            parent_widget = parent if isinstance(parent, QWidget) else None
        
        self.widget = QPushButton(self._text, parent_widget)
        self.widget.clicked.connect(self.callback)
        return self.widget


class CheckButton(Widget):
    """Qt Checkbox widget."""
    def __init__(self, text='', value=False, callback=None):
        self._text = text
        self._initial_value = value
        self._callback = callback
        self.var = _BoolVar(value)

    def create(self, parent):
        if isinstance(parent, (QVBoxLayout, QHBoxLayout, QGridLayout)):
            parent_widget = parent.parentWidget()
        else:
            parent_widget = parent if isinstance(parent, QWidget) else None
        
        self.widget = QCheckBox(self._text, parent_widget)
        self.widget.setChecked(self._initial_value)
        self.var._widget = self.widget
        
        if self._callback:
            self.widget.stateChanged.connect(lambda state: self._callback())
        
        return self.widget

    @property
    def value(self):
        if self.widget:
            return self.widget.isChecked()
        return self._initial_value


class _BoolVar:
    """Mimics tkinter BooleanVar for compatibility."""
    def __init__(self, value=False):
        self._value = value
        self._widget = None

    def get(self):
        if self._widget:
            return self._widget.isChecked()
        return self._value

    def set(self, value):
        self._value = value
        if self._widget:
            self._widget.setChecked(value)


class _IntVar:
    """Mimics tkinter IntVar for compatibility."""
    def __init__(self, value=0):
        self._value = value
        self._widgets = []

    def get(self):
        return self._value

    def set(self, value):
        self._value = value
        for w in self._widgets:
            if hasattr(w, 'setChecked'):
                w.setChecked(w.property('_radio_value') == value)


class SpinBox(Widget):
    """Qt SpinBox widget."""
    def __init__(self, value, start, end, step, callback=None,
                 rounding=None, width=6):
        self._initial = value
        self._start = start
        self._end = end
        self._step = step
        self._callback = callback
        self._rounding = rounding
        self._width = width
        self._is_float = isinstance(value, float) or isinstance(step, float) or '.' in str(step)

    def create(self, parent):
        if isinstance(parent, (QVBoxLayout, QHBoxLayout, QGridLayout)):
            parent_widget = parent.parentWidget()
        else:
            parent_widget = parent if isinstance(parent, QWidget) else None
        
        if self._is_float:
            self.widget = QDoubleSpinBox(parent_widget)
            self.widget.setDecimals(self._rounding if self._rounding else 2)
            self.widget.setSingleStep(float(self._step))
            self.widget.setRange(float(self._start), float(self._end))
            self.widget.setValue(float(self._initial))
        else:
            self.widget = QSpinBox(parent_widget)
            self.widget.setSingleStep(int(self._step))
            self.widget.setRange(int(self._start), int(self._end))
            self.widget.setValue(int(self._initial))
        
        # Set width
        self.widget.setFixedWidth(self._width * 15)
        
        if self._callback:
            self.widget.valueChanged.connect(lambda val: self._callback())
        
        return self.widget

    @property
    def value(self):
        if self.widget:
            return self.widget.value()
        return self._initial

    @value.setter
    def value(self, x):
        if self.widget:
            if self._is_float:
                self.widget.setValue(float(x) if x is not None else 0.0)
            else:
                self.widget.setValue(int(x) if x is not None else 0)


class Entry(Widget):
    """Qt LineEdit widget."""
    def __init__(self, value='', width=20, callback=None):
        self._initial = str(value)
        self._width = width
        self._callback = callback

    def create(self, parent):
        if isinstance(parent, (QVBoxLayout, QHBoxLayout, QGridLayout)):
            parent_widget = parent.parentWidget()
        else:
            parent_widget = parent if isinstance(parent, QWidget) else None
        
        self.widget = QLineEdit(parent_widget)
        self.widget.setText(self._initial)
        self.widget.setFixedWidth(self._width * 10)
        
        if self._callback:
            self.widget.returnPressed.connect(self._callback)
        
        # Alias for compatibility
        self.entry = self.widget
        return self.widget

    @property
    def value(self):
        if self.widget:
            return self.widget.text()
        return self._initial

    @value.setter
    def value(self, x):
        if self.widget:
            self.widget.setText(str(x))


class Scale(Widget):
    """Qt Slider widget."""
    def __init__(self, value, start, end, callback):
        self._initial = value
        self._start = start
        self._end = end
        self._callback = callback

    def create(self, parent):
        if isinstance(parent, (QVBoxLayout, QHBoxLayout, QGridLayout)):
            parent_widget = parent.parentWidget()
        else:
            parent_widget = parent if isinstance(parent, QWidget) else None
        
        self.widget = QSlider(Qt.Horizontal, parent_widget)
        self.widget.setRange(int(self._start), int(self._end))
        self.widget.setValue(int(self._initial))
        
        if self._callback:
            self.widget.valueChanged.connect(self._callback)
        
        self.scale = self.widget  # Alias for compatibility
        return self.widget

    @property
    def value(self):
        if self.widget:
            return self.widget.value()
        return self._initial

    @value.setter
    def value(self, x):
        if self.widget:
            self.widget.setValue(int(x))


class RadioButtons(Widget):
    """Container for multiple radio buttons."""
    def __init__(self, labels, values=None, callback=None, vertical=False):
        self.var = _IntVar()
        self._callback = callback
        self.values = values or list(range(len(labels)))
        self._labels = labels
        self._vertical = vertical
        self.buttons = []

    def create(self, parent):
        if isinstance(parent, (QVBoxLayout, QHBoxLayout, QGridLayout)):
            parent_widget = parent.parentWidget()
        else:
            parent_widget = parent if isinstance(parent, QWidget) else None
        
        self.widget = QWidget(parent_widget)
        if self._vertical:
            layout = QVBoxLayout()
        else:
            layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.widget.setLayout(layout)
        
        self._button_group = QButtonGroup(self.widget)
        
        for i, label in enumerate(self._labels):
            rb = QRadioButton(label, self.widget)
            rb.setProperty('_radio_value', i)
            self._button_group.addButton(rb, i)
            layout.addWidget(rb)
            self.buttons.append(rb)
            self.var._widgets.append(rb)
        
        if self.buttons:
            self.buttons[0].setChecked(True)
        
        if self._callback:
            self._button_group.buttonClicked.connect(
                lambda btn: self._callback(self.value)
            )
        
        return self.widget

    @property
    def value(self):
        checked_id = self._button_group.checkedId() if hasattr(self, '_button_group') else 0
        if 0 <= checked_id < len(self.values):
            return self.values[checked_id]
        return self.values[0] if self.values else 0

    @value.setter
    def value(self, value):
        if value in self.values:
            idx = self.values.index(value)
            if idx < len(self.buttons):
                self.buttons[idx].setChecked(True)
                self.var.set(idx)

    def __getitem__(self, value):
        if value in self.values:
            idx = self.values.index(value)
            return self.buttons[idx]
        return None


class RadioButton(Widget):
    """Single radio button (usually part of RadioButtons)."""
    def __init__(self, label, i, var, callback):
        self._label = label
        self._index = i
        self._var = var
        self._callback = callback

    def create(self, parent):
        if isinstance(parent, (QVBoxLayout, QHBoxLayout, QGridLayout)):
            parent_widget = parent.parentWidget()
        else:
            parent_widget = parent if isinstance(parent, QWidget) else None
        
        self.widget = QRadioButton(self._label, parent_widget)
        self.widget.setProperty('_radio_value', self._index)
        
        if self._callback:
            self.widget.clicked.connect(self._callback)
        
        return self.widget


class ComboBox(Widget):
    """Qt ComboBox widget."""
    def __init__(self, labels, values=None, callback=None):
        self.values = values or list(range(len(labels)))
        self._labels = labels
        self._callback = callback
        self._initial_value = None  # Store initial value to set after widget creation

    def create(self, parent):
        if isinstance(parent, (QVBoxLayout, QHBoxLayout, QGridLayout)):
            parent_widget = parent.parentWidget()
        else:
            parent_widget = parent if isinstance(parent, QWidget) else None
        
        self.widget = QComboBox(parent_widget)
        for label in self._labels:
            self.widget.addItem(label)
        
        # Apply initial value if it was set before widget creation
        if self._initial_value is not None and self._initial_value in self.values:
            idx = self.values.index(self._initial_value)
            self.widget.setCurrentIndex(idx)
        
        if self._callback:
            self.widget.currentIndexChanged.connect(
                lambda idx: self._callback(self.value)
            )
        
        return self.widget

    @property
    def value(self):
        if self.widget:
            idx = self.widget.currentIndex()
            if 0 <= idx < len(self.values):
                return self.values[idx]
        return self._initial_value if self._initial_value else (self.values[0] if self.values else None)

    @value.setter
    def value(self, val):
        self._initial_value = val  # Always store it
        if self.widget and val in self.values:
            idx = self.values.index(val)
            self.widget.setCurrentIndex(idx)


class Rows(Widget):
    """Vertical container for rows of widgets."""
    def __init__(self, rows=None):
        self.rows_to_be_added = rows or []
        self.rows = []
        self._layout = None

    def create(self, parent):
        if isinstance(parent, (QVBoxLayout, QHBoxLayout, QGridLayout)):
            parent_widget = parent.parentWidget()
        else:
            parent_widget = parent if isinstance(parent, QWidget) else None
        
        self.widget = QWidget(parent_widget)
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.widget.setLayout(self._layout)
        
        for row in self.rows_to_be_added:
            self.add(row)
        self.rows_to_be_added = []
        
        return self.widget

    def add(self, row):
        if isinstance(row, str):
            row = Label(row)
        elif isinstance(row, list):
            row = Row(row)
        row.pack(self._layout)
        self.rows.append(row)

    def clear(self):
        while self.rows:
            del self[0]

    def __getitem__(self, i):
        return self.rows[i]

    def __delitem__(self, i):
        row = self.rows.pop(i)
        if row.widget:
            row.widget.setParent(None)
            row.widget.deleteLater()

    def __len__(self):
        return len(self.rows)


class MenuItem:
    """Menu item definition for Qt menus."""
    def __init__(self, label, callback=None, key=None,
                 value=None, choices=None, submenu=None, disabled=False):
        self.underline = label.find('_')
        self.label = label.replace('_', '')
        self.callback = callback
        self.key = key
        self.keyname = None
        self.value = value
        self.choices = choices
        self.submenu = submenu
        self.disabled = disabled

        # Parse keyboard shortcut
        if key:
            is_macos = platform.system() == 'Darwin'
            parts = key.split('+')
            qt_parts = []
            
            for part in parts:
                if part == 'Ctrl':
                    qt_parts.append('Ctrl' if not is_macos else 'Meta')
                elif part == 'Alt':
                    qt_parts.append('Alt' if not is_macos else 'Ctrl')
                elif part == 'Shift':
                    qt_parts.append('Shift')
                else:
                    qt_parts.append(part)
            
            self.keyname = '+'.join(qt_parts)
            if is_macos:
                self.key = key.replace('Alt', 'Command')

    def addto(self, menu, window, stuff=None):
        if self.label == '---':
            menu.addSeparator()
        elif self.value is not None:
            # Checkable action
            action = QAction(self.label, window)
            action.setCheckable(True)
            action.setChecked(self.value)
            if self.keyname:
                action.setShortcut(QKeySequence(self.keyname))
            action.triggered.connect(lambda checked: self.callback())
            menu.addAction(action)
            if stuff is not None:
                stuff[self.callback.__name__.replace('_', '-')] = action
        elif self.choices:
            # Submenu with radio choices
            submenu = menu.addMenu(self.label)
            action_group = QActionGroup(window)
            action_group.setExclusive(True)
            for i, choice in enumerate(self.choices):
                action = QAction(choice.replace('_', ''), window)
                action.setCheckable(True)
                if i == 0:
                    action.setChecked(True)
                action.setData(i)
                action.triggered.connect(lambda checked, idx=i: self.callback())
                action_group.addAction(action)
                submenu.addAction(action)
            if stuff is not None:
                stuff[self.callback.__name__.replace('_', '-')] = action_group
        elif self.submenu:
            # Cascading submenu
            submenu = menu.addMenu(self.label)
            for thing in self.submenu:
                thing.addto(submenu, window, stuff)
        else:
            # Regular action
            action = QAction(self.label, window)
            if self.keyname:
                action.setShortcut(QKeySequence(self.keyname))
            action.setEnabled(not self.disabled)
            if self.callback:
                action.triggered.connect(lambda checked: self.callback())
            menu.addAction(action)


class MainWindow(BaseWindow):
    """Qt Main Window."""
    def __init__(self, title, close=None, menu=[]):
        get_app()
        self.win = QMainWindow()
        self.menu = {}
        self._dnd_available = True  # Qt has built-in DnD support
        
        super().__init__(title, close)
        
        if menu:
            self.create_menu(menu)

    def create_menu(self, menu_description):
        menubar = self.win.menuBar()
        
        for label, things in menu_description:
            menu = menubar.addMenu(label.replace('_', ''))
            for thing in things:
                thing.addto(menu, self.win, self.menu)

    def run(self):
        self.win.show()
        get_app().exec_()

    def __getitem__(self, name):
        item = self.menu.get(name)
        if item:
            if hasattr(item, 'isChecked'):
                return item.isChecked()
            elif hasattr(item, 'checkedAction'):
                action = item.checkedAction()
                return action.data() if action else 0
        return False

    def get(self, name, default=None):
        """Get menu item value with a default if not found."""
        item = self.menu.get(name)
        if item:
            if hasattr(item, 'isChecked'):
                return item.isChecked()
            elif hasattr(item, 'checkedAction'):
                action = item.checkedAction()
                return action.data() if action else 0
        return default if default is not None else False

    def __setitem__(self, name, value):
        item = self.menu.get(name)
        if item:
            if hasattr(item, 'setChecked'):
                item.setChecked(value)


# File dialog compatibility
def LoadFileDialog(parent, title):
    """Compatibility wrapper for file open dialog."""
    return _FileDialogWrapper(parent, title, 'open')


def SaveFileDialog(parent, title):
    """Compatibility wrapper for file save dialog."""
    return _FileDialogWrapper(parent, title, 'save')


class _FileDialogWrapper:
    def __init__(self, parent, title, mode):
        self.parent = parent
        self.title = title
        self.mode = mode
        self.format = None

    def go(self, default=''):
        if self.mode == 'open':
            filename, _ = QFileDialog.getOpenFileName(
                self.parent if isinstance(self.parent, QWidget) else None,
                self.title,
                default
            )
        else:
            filename, _ = QFileDialog.getSaveFileName(
                self.parent if isinstance(self.parent, QWidget) else None,
                self.title,
                default
            )
        return filename if filename else None


class ASEFileChooser:
    """File chooser with format selection."""
    def __init__(self, win, formatcallback=lambda event: None):
        from ase.io.formats import all_formats, get_ioformat
        
        self.win = win
        self.format = None
        self._labels = [_('Automatic')]
        self._values = ['']

        def key(item):
            return item[1][0]

        for format, (description, code) in sorted(all_formats.items(), key=key):
            io = get_ioformat(format)
            if io.can_read and description != '?':
                self._labels.append(_(description))
                self._values.append(format)

    def go(self, default=''):
        # For now, use simple file dialog
        # Could be extended to show format selection
        filename, _ = QFileDialog.getOpenFileName(
            None, _('Open ...'), default
        )
        return filename if filename else None


def show_io_error(filename, err):
    showerror(_('Read error'), _(f'Could not read {filename}: {err}'))


def bind(callback, modifier=None):
    """Event binding wrapper for Qt."""
    def handle(event):
        # Create a compatible event object
        class QtEventWrapper:
            def __init__(self, qevent):
                self.button = getattr(qevent, 'button', lambda: 0)()
                self.key = ''
                self.modifier = modifier
                self.x = getattr(qevent, 'x', lambda: 0)()
                self.y = getattr(qevent, 'y', lambda: 0)()
        callback(QtEventWrapper(event))
    return handle


def bind_enter(widget, callback):
    """Bind Return/Enter key to widget."""
    if hasattr(widget, 'returnPressed'):
        widget.returnPressed.connect(callback)


# Placeholder for ASEGUIWindow - will be implemented in view_qt.py
# This is a complex class that requires the canvas implementation
class ASEGUIWindow(MainWindow):
    """Main ASE-GUI window with canvas for atom visualization."""
    
    def __init__(self, close, menu, config,
                 scroll, scroll_event,
                 press, move, release, resize,
                 open_callback=None,
                 workspace_mode=False):
        super().__init__('ASE-GUI', close, menu)
        
        self.size = np.array([450, 450])
        self.fg = config['gui_foreground_color']
        self.bg = config['gui_background_color']
        self.open_callback = open_callback
        self.workspace_mode = workspace_mode
        
        # Store callbacks
        self._scroll = scroll
        self._scroll_event = scroll_event
        self._press = press
        self._move = move
        self._release = release
        self._resize = resize
        
        # Create central widget with layout
        central = QWidget()
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        central.setLayout(self.main_layout)
        self.win.setCentralWidget(central)
        
        # Create sidebar if workspace mode
        self.sidebar_frame = None
        self.paned_window = None
        
        if workspace_mode:
            self.paned_window = QSplitter(Qt.Horizontal)
            self.paned_window.setChildrenCollapsible(False)
            
            self.sidebar_frame = QWidget()
            self.sidebar_frame.setMinimumWidth(200)
            sidebar_layout = QVBoxLayout()
            sidebar_layout.setContentsMargins(0, 0, 0, 0)
            self.sidebar_frame.setLayout(sidebar_layout)
            self.paned_window.addWidget(self.sidebar_frame)
            
            canvas_container = QWidget()
            canvas_layout = QVBoxLayout()
            canvas_layout.setContentsMargins(0, 0, 0, 0)
            canvas_container.setLayout(canvas_layout)
            
            self.canvas = _QtCanvas(self, config)
            canvas_layout.addWidget(self.canvas)
            self.paned_window.addWidget(canvas_container)
            
            # Set stretch factors so canvas expands more than sidebar
            self.paned_window.setStretchFactor(0, 0)  # Sidebar doesn't stretch
            self.paned_window.setStretchFactor(1, 1)  # Canvas stretches
            self.paned_window.setSizes([250, 450])
            self.main_layout.addWidget(self.paned_window, 1)  # stretch factor 1
        else:
            self.canvas = _QtCanvas(self, config)
            self.main_layout.addWidget(self.canvas, 1)  # stretch factor 1
        
        # Status bar
        self.status = QStatusBar()
        self.win.setStatusBar(self.status)
        
        # Enable drag and drop
        self.win.setAcceptDrops(True)
        
        # Connect canvas events
        self._connect_events()
    
    def _connect_events(self):
        """Connect Qt events to callbacks."""
        # Events are handled by _QtCanvas
        pass

    def update_status_line(self, text):
        self.status.showMessage(text)

    def clear(self):
        self.canvas.clear()

    def update(self):
        # Use repaint() for immediate synchronous painting
        self.canvas.repaint()

    def circle(self, color, selected, *bbox, constrained=False):
        self.canvas.add_circle(color, selected, bbox, constrained=constrained)

    def arc(self, color, selected, start, extent, *bbox):
        self.canvas.add_arc(color, selected, start, extent, bbox)

    def line(self, bbox, width=1):
        self.canvas.add_line(bbox, width)

    def text(self, x, y, txt, anchor='center', color='black'):
        self.canvas.add_text(x, y, txt, anchor, color)

    def after(self, time, callback):
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(callback)
        timer.start(int(time * 1000))
        return namedtuple('Timer', 'cancel')(timer.stop)

    def run(self):
        self.win.show()
        get_app().exec_()


class _QtCanvas(QWidget):
    """Custom Qt widget for atom rendering."""
    
    def __init__(self, parent_window, config):
        super().__init__()
        self.parent_window = parent_window
        self.config = config
        self.setMinimumSize(450, 450)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Enable double buffering for flicker-free rendering
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        
        # Drawing primitives storage - single list preserving z-order
        self._primitives = []  # List of (type, data) tuples
        self._texts = []
        self._selection_rect = None  # For selection rectangle during drag
        
        # Set background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(config['gui_background_color']))
        self.setPalette(palette)
        
        # Enable mouse tracking
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
    
    def clear(self):
        self._primitives = []
        self._texts = []
        self._selection_rect = None
        # Don't call update() here - wait for the draw cycle to complete
        # The final update() call in Window.update() will trigger the repaint
    
    def create_rectangle(self, bbox):
        """Create a selection rectangle for atom selection."""
        self._selection_rect = bbox
        self.update()
    
    def add_circle(self, color, selected, bbox, constrained=False):
        self._primitives.append(('circle', (color, selected, bbox, constrained)))
    
    def add_arc(self, color, selected, start, extent, bbox):
        self._primitives.append(('arc', (color, selected, start, extent, bbox)))
    
    def add_line(self, bbox, width):
        self._primitives.append(('line', (bbox, width)))
    
    def add_text(self, x, y, txt, anchor, color):
        self._texts.append((x, y, txt, anchor, color))
    
    def paintEvent(self, event):
        from PyQt5.QtGui import QRadialGradient, QPainterPath
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Check if 3D rendering is enabled (key is derived from callback name)
        render_3d = self.parent_window.get('toggle-3d-rendering', True)
        
        # Draw all primitives in z-order (as they were added)
        for ptype, pdata in self._primitives:
            if ptype == 'circle':
                color, selected, bbox, constrained = pdata
                x1, y1, x2, y2 = [int(v) for v in bbox]
                
                diameter = x2 - x1
                radius = diameter / 2.0
                cx = x1 + radius
                cy = y1 + radius
                
                base_color = QColor(color)
                
                if render_3d:
                    # 3D spherical look with radial gradient
                    highlight_x = cx - radius * 0.35
                    highlight_y = cy - radius * 0.35
                    
                    gradient = QRadialGradient(cx, cy, radius, highlight_x, highlight_y)
                    
                    highlight_color = base_color.lighter(150)
                    shadow_color = base_color.darker(140)
                    
                    gradient.setColorAt(0.0, highlight_color)
                    gradient.setColorAt(0.5, base_color)
                    gradient.setColorAt(1.0, shadow_color)
                    
                    if selected:
                        pen = QPen(QColor('#004500'), 3)
                    else:
                        pen = QPen(shadow_color.darker(120), 1)
                    
                    painter.setPen(pen)
                    painter.setBrush(QBrush(gradient))
                else:
                    # 2D flat rendering (original style)
                    if selected:
                        pen = QPen(QColor('#004500'), 3)
                    else:
                        pen = QPen(QColor('black'), 1)
                    
                    painter.setPen(pen)
                    painter.setBrush(QBrush(base_color))
                
                # Draw the atom circle/sphere
                painter.drawEllipse(x1, y1, diameter, diameter)
                
                # Draw constraint cross (clipped to circle)
                if constrained:
                    clip_path = QPainterPath()
                    clip_path.addEllipse(float(x1), float(y1), float(diameter), float(diameter))
                    painter.save()
                    painter.setClipPath(clip_path)
                    painter.setPen(QPen(QColor('black'), 1))
                    R1 = int(0.14644 * diameter)
                    R2 = int(0.85355 * diameter)
                    painter.drawLine(x1 + R1, y1 + R1, x1 + R2, y1 + R2)
                    painter.drawLine(x1 + R2, y1 + R1, x1 + R1, y1 + R2)
                    painter.restore()
            
            elif ptype == 'arc':
                color, selected, start, extent, bbox = pdata
                x1, y1, x2, y2 = [int(v) for v in bbox]
                
                if selected:
                    pen = QPen(QColor('#004500'), 3)
                else:
                    pen = QPen(QColor('black'), 1)
                
                painter.setPen(pen)
                painter.setBrush(QBrush(QColor(color)))
                # Qt uses 1/16th of a degree for arc angles
                painter.drawPie(x1, y1, x2 - x1, y2 - y1, int(start * 16), int(extent * 16))
            
            elif ptype == 'line':
                bbox, width = pdata
                x1, y1, x2, y2 = [int(v) for v in bbox]
                painter.setPen(QPen(QColor('black'), width))
                painter.drawLine(x1, y1, x2, y2)
        
        # Draw text (labels) - always on top
        for x, y, txt, anchor, color in self._texts:
            painter.setPen(QPen(QColor(color)))
            painter.drawText(int(x), int(y), txt)
        
        # Draw selection rectangle if active
        if self._selection_rect:
            x1, y1, x2, y2 = [int(v) for v in self._selection_rect]
            painter.setPen(QPen(QColor('blue'), 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
        
        painter.end()
    
    def mousePressEvent(self, event):
        if self.parent_window._press:
            wrapped = _wrap_mouse_event(event)
            self.parent_window._press(wrapped)
    
    def mouseMoveEvent(self, event):
        if self.parent_window._move:
            wrapped = _wrap_mouse_event(event)
            self.parent_window._move(wrapped)
    
    def mouseReleaseEvent(self, event):
        # Clear selection rectangle on mouse release
        self._selection_rect = None
        
        if self.parent_window._release:
            wrapped = _wrap_mouse_event(event)
            self.parent_window._release(wrapped)
    
    def wheelEvent(self, event):
        if self.parent_window._scroll_event:
            wrapped = _wrap_wheel_event(event)
            self.parent_window._scroll_event(wrapped)
    
    def keyPressEvent(self, event):
        if self.parent_window._scroll:
            wrapped = _wrap_key_event(event)
            self.parent_window._scroll(wrapped)
    
    def resizeEvent(self, event):
        if self.parent_window._resize:
            self.parent_window._resize(event)
        super().resizeEvent(event)


def _wrap_mouse_event(event):
    """Wrap Qt mouse event to be compatible with Tk event structure."""
    import time
    
    class WrappedEvent:
        pass
    
    wrapped = WrappedEvent()
    wrapped.x = event.x()
    wrapped.y = event.y()
    
    # Handle both click events (button()) and drag events (buttons())
    button = event.button()
    if button == Qt.NoButton:
        # During drag, use buttons() to get currently held button
        buttons = event.buttons()
        if buttons & Qt.LeftButton:
            button = Qt.LeftButton
        elif buttons & Qt.MiddleButton:
            button = Qt.MiddleButton
        elif buttons & Qt.RightButton:
            button = Qt.RightButton
    
    wrapped.button = {
        Qt.LeftButton: 1,
        Qt.MiddleButton: 2,
        Qt.RightButton: 3
    }.get(button, 1)
    
    # Set modifier
    wrapped.modifier = None
    if event.modifiers() & Qt.ControlModifier:
        wrapped.modifier = 'ctrl'
    elif event.modifiers() & Qt.ShiftModifier:
        wrapped.modifier = 'shift'
    
    wrapped.key = ''
    # Timestamp in milliseconds (Tk uses ms)
    wrapped.time = int(time.time() * 1000)
    return wrapped


def _wrap_wheel_event(event):
    """Wrap Qt wheel event."""
    class WrappedEvent:
        pass
    
    wrapped = WrappedEvent()
    wrapped.x = event.x()
    wrapped.y = event.y()
    # Qt wheel delta is in 1/8 degree steps, 120 = 15 degrees = 1 step
    wrapped.delta = event.angleDelta().y()
    wrapped.button = 0
    wrapped.modifier = None
    wrapped.key = ''
    return wrapped


def _wrap_key_event(event):
    """Wrap Qt key event."""
    class WrappedEvent:
        pass
    
    wrapped = WrappedEvent()
    wrapped.x = 0
    wrapped.y = 0
    wrapped.button = 0
    wrapped.key = event.text().lower() if event.text() else ''
    # Tk event type '2' is KeyPress, '6' is Motion (mouse)
    wrapped.type = '2'  # KeyPress event type
    
    # Map special keys
    key_map = {
        Qt.Key_Left: 'left',
        Qt.Key_Right: 'right',
        Qt.Key_Up: 'up',
        Qt.Key_Down: 'down',
        Qt.Key_Home: 'home',
        Qt.Key_End: 'end',
        Qt.Key_PageUp: 'prior',
        Qt.Key_PageDown: 'next',
        Qt.Key_Delete: 'delete',
        Qt.Key_Backspace: 'backspace',
    }
    if event.key() in key_map:
        wrapped.key = key_map[event.key()]
    
    # Build Tk-compatible state bitmask for modifier detection
    # Tk uses: 0x1 = Shift, 0x4 = Ctrl, 0x8 = Alt/Meta, 0x10 = Mac Option
    wrapped.state = 0
    modifiers = event.modifiers()
    if modifiers & Qt.ShiftModifier:
        wrapped.state |= 0x1
    if modifiers & Qt.ControlModifier:
        wrapped.state |= 0x4
    if modifiers & Qt.AltModifier:
        wrapped.state |= 0x8
    if modifiers & Qt.MetaModifier:
        wrapped.state |= 0x10
    
    wrapped.modifier = None
    if modifiers & Qt.ControlModifier:
        wrapped.modifier = 'ctrl'
    elif modifiers & Qt.ShiftModifier:
        wrapped.modifier = 'shift'
    
    return wrapped


class TabControl(Widget):
    """Qt Tab control widget."""
    
    def __init__(self, parent, switch_callback, gui=None):
        self.switch_callback = switch_callback
        self.gui = gui
        self.tabs = {}
        self.filepaths = {}
        self._parent = parent
        self._programmatic_switch = False  # Flag to prevent callback loop
        
        if isinstance(parent, QWidget):
            self.notebook = QTabWidget(parent)
        else:
            self.notebook = QTabWidget()
        
        self.notebook.currentChanged.connect(self._on_tab_change)
        self.notebook.setContextMenuPolicy(Qt.CustomContextMenu)
        self.notebook.customContextMenuRequested.connect(self._on_right_click)
    
    def pack(self, **kwargs):
        # Qt uses different layout mechanism
        # Handle QMainWindow specially - need to use central widget's layout
        if hasattr(self._parent, 'centralWidget'):
            central = self._parent.centralWidget()
            if central and central.layout():
                # Insert at position 0 to put tabs above canvas (no stretch)
                central.layout().insertWidget(0, self.notebook, 0)
                return
        if self._parent and hasattr(self._parent, 'layout'):
            layout = self._parent.layout()
            if layout:
                layout.addWidget(self.notebook, 0)  # No stretch for tab bar
    
    def add_tab(self, title, filepath=None):
        """Add a new tab with title."""
        frame = QWidget()
        tab_id = len(self.tabs)
        self.notebook.addTab(frame, title)
        self.tabs[tab_id] = frame
        if filepath is not None:
            self.filepaths[tab_id] = filepath
        return tab_id
    
    def _on_tab_change(self, index):
        # Skip callback if this was a programmatic switch
        if self._programmatic_switch:
            return
        if self.switch_callback is not None:
            try:
                self.switch_callback(index)
            except Exception:
                pass
    
    def _on_right_click(self, pos):
        """Show context menu when right-clicking on a tab."""
        tab_index = self.notebook.tabBar().tabAt(pos)
        if tab_index < 0:
            return
        
        menu = QMenu()
        
        if tab_index > 0:
            menu.addAction("Move Left", lambda: self._move_tab(tab_index, -1))
        
        if tab_index < self.notebook.count() - 1:
            menu.addAction("Move Right", lambda: self._move_tab(tab_index, 1))
        
        if tab_index > 0 or tab_index < self.notebook.count() - 1:
            menu.addSeparator()
        
        menu.addAction("Move to New Window", lambda: self._move_to_new_window(tab_index))
        menu.addSeparator()
        menu.addAction("Close", lambda: self._close_tab_by_index(tab_index))
        
        menu.exec_(self.notebook.mapToGlobal(pos))
    
    def _move_tab(self, tab_index, direction):
        new_index = tab_index + direction
        if 0 <= new_index < self.notebook.count():
            widget = self.notebook.widget(tab_index)
            text = self.notebook.tabText(tab_index)
            self.notebook.removeTab(tab_index)
            self.notebook.insertTab(new_index, widget, text)
            self.notebook.setCurrentIndex(new_index)
    
    def _move_to_new_window(self, tab_index):
        if self.gui and hasattr(self.gui, 'move_tab_to_new_window'):
            self.gui.move_tab_to_new_window(tab_index)
    
    def _close_tab_by_index(self, tab_index):
        if self.gui and hasattr(self.gui, 'close_tab_by_index'):
            self.gui.close_tab_by_index(tab_index)
    
    def remove_tab(self, tab_id):
        """Remove a tab by its tab_id."""
        if tab_id not in self.tabs:
            return False
        
        widget = self.tabs[tab_id]
        for i in range(self.notebook.count()):
            if self.notebook.widget(i) == widget:
                self.notebook.removeTab(i)
                break
        
        del self.tabs[tab_id]
        if tab_id in self.filepaths:
            del self.filepaths[tab_id]
        
        return True

    def select_tab(self, tab_id):
        """Programmatically select a tab by its tab_id."""
        if tab_id not in self.tabs:
            return False
        
        widget = self.tabs[tab_id]
        for i in range(self.notebook.count()):
            if self.notebook.widget(i) == widget:
                # Use flag to prevent callback loop
                self._programmatic_switch = True
                self.notebook.setCurrentIndex(i)
                self._programmatic_switch = False
                return True
        return False
