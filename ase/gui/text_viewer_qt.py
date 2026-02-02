# fmt: off

"""Qt Text viewer for ASE-GUI workspace mode.

Displays text files (INCAR, KPOINTS, etc.) in a read-only viewer.
"""

from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QLabel, QWidget, QScrollArea
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt


class TextViewer:
    """Simple text file viewer with syntax highlighting (Qt version)."""
    
    def __init__(self, parent, title='Text Viewer'):
        """Initialize text viewer.
        
        Args:
            parent: Parent Qt widget
            title: Window title
        """
        # Create window
        self.window = QDialog(parent)
        self.window.setWindowTitle(title)
        self.window.resize(800, 600)
        
        layout = QVBoxLayout(self.window)
        
        # Create toolbar frame
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(5, 2, 5, 2)
        
        # File label
        self.file_label = QLabel('')
        toolbar_layout.addWidget(self.file_label, stretch=1)
        
        # Reload button
        self.reload_btn = QPushButton('Reload')
        self.reload_btn.clicked.connect(self.reload)
        toolbar_layout.addWidget(self.reload_btn)
        
        layout.addWidget(toolbar)
        
        # Create text widget
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont('Courier', 10))
        self.text.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(self.text)
        
        self.current_file = None
        
        # Keyword highlighting
        self.keywords = {}
        self.setup_syntax_rules()
    
    def setup_syntax_rules(self):
        """Set up basic syntax highlighting rules."""
        # Colors for VASP files
        self.keywords = {
            # INCAR keywords
            'ENCUT': 'blue',
            'EDIFF': 'blue',
            'ISMEAR': 'blue',
            'SIGMA': 'blue',
            'IBRION': 'blue',
            'NSW': 'blue',
            'ISIF': 'blue',
            'PREC': 'blue',
            'ALGO': 'blue',
            'LREAL': 'blue',
            'LWAVE': 'blue',
            'LCHARG': 'blue',
            'NELM': 'blue',
            'NELMIN': 'blue',
            'EDIFFG': 'blue',
            'POTIM': 'blue',
            'NCORE': 'blue',
            'KPAR': 'blue',
            'NPAR': 'blue',
            'LORBIT': 'blue',
            'NEDOS': 'blue',
            'ISPIN': 'blue',
            'MAGMOM': 'blue',
            'LDAU': 'blue',
            'LDAUU': 'blue',
            'LDAUJ': 'blue',
            'LDAUL': 'blue',
            'LDAUTYPE': 'blue',
            'LDAUPRINT': 'blue',
            'LMAXMIX': 'blue',
            'IVDW': 'blue',
            'VDW_RADIUS': 'blue',
            'LASPH': 'blue',
            'ADDGRID': 'blue',
            'LAECHG': 'blue',
            'ISTART': 'blue',
            'ICHARG': 'blue',
            'NBANDS': 'blue',
            'EMIN': 'blue',
            'EMAX': 'blue',
            'LOPTICS': 'blue',
            'LPEAD': 'blue',
            'LEPSILON': 'blue',
            'LRPA': 'blue',
            'CSHIFT': 'blue',
            'NBANDSO': 'blue',
            'NBANDSV': 'blue',
            'OMEGAMAX': 'blue',
            'LSPECTRA': 'blue',
            'LBERRY': 'blue',
            'IGPAR': 'blue',
            'NPPSTR': 'blue',
            'DIPOL': 'blue',
            'IDIPOL': 'blue',
            'LDIPOL': 'blue',
            'EFIELD': 'blue',
            'NGX': 'blue',
            'NGY': 'blue',
            'NGZ': 'blue',
            'NGXF': 'blue',
            'NGYF': 'blue',
            'NGZF': 'blue',
            'SYMPREC': 'blue',
            'ISYM': 'blue',
            'GGA': 'blue',
            'METAGGA': 'blue',
            'LHFCALC': 'blue',
            'AEXX': 'blue',
            'AGGAX': 'blue',
            'AGGAC': 'blue',
            'ALDAC': 'blue',
            # Boolean values
            '.TRUE.': 'green',
            '.FALSE.': 'green',
            'True': 'green',
            'False': 'green',
        }
    
    def load_file(self, filepath):
        """Load a file into the viewer.
        
        Args:
            filepath: Path to file to load
        """
        filepath = Path(filepath)
        self.current_file = filepath
        
        # Update label
        self.file_label.setText(str(filepath))
        self.window.setWindowTitle(f'Text Viewer - {filepath.name}')
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            content = f'Error loading file: {e}'
        
        # Set text
        self.text.setPlainText(content)
    
    def reload(self):
        """Reload the current file."""
        if self.current_file:
            self.load_file(self.current_file)
    
    def show(self):
        """Show the viewer window."""
        self.window.show()
    
    def close(self):
        """Close the viewer window."""
        self.window.close()
