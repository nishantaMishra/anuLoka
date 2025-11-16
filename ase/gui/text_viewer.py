# fmt: off

"""Text viewer for ASE-GUI workspace mode.

Displays text files (INCAR, KPOINTS, etc.) in a read-only viewer.
"""

import tkinter as tk
import tkinter.scrolledtext as scrolledtext
from pathlib import Path


class TextViewer:
    """Simple text file viewer with syntax highlighting."""
    
    def __init__(self, parent, title='Text Viewer'):
        """Initialize text viewer.
        
        Args:
            parent: Parent tkinter widget
            title: Window title
        """
        # Create window
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry('800x600')
        
        # Create toolbar frame
        toolbar = tk.Frame(self.window, bg='#f0f0f0', height=30)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        toolbar.pack_propagate(False)
        
        # File label
        self.file_label = tk.Label(
            toolbar,
            text='',
            bg='#f0f0f0',
            anchor=tk.W,
            padx=10
        )
        self.file_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Reload button
        self.reload_btn = tk.Button(
            toolbar,
            text='Reload',
            command=self.reload,
            bg='#f0f0f0',
            relief=tk.FLAT,
            padx=10
        )
        self.reload_btn.pack(side=tk.RIGHT)
        
        # Create text widget with scrollbar
        self.text = scrolledtext.ScrolledText(
            self.window,
            wrap=tk.NONE,
            font=('Courier', 10),
            bg='white',
            fg='black'
        )
        self.text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Make read-only
        self.text.bind('<Key>', lambda e: 'break')
        
        # Configure tags for syntax highlighting
        self._configure_tags()
        
        # Current file path
        self.current_file = None
    
    def _configure_tags(self):
        """Configure text tags for basic syntax highlighting."""
        # Comments
        self.text.tag_config('comment', foreground='#008000')
        # Keywords
        self.text.tag_config('keyword', foreground='#0000ff', font=('Courier', 10, 'bold'))
        # Numbers
        self.text.tag_config('number', foreground='#ff0000')
        # Strings
        self.text.tag_config('string', foreground='#a31515')
        # Headers/Sections
        self.text.tag_config('header', foreground='#0000ff', font=('Courier', 10, 'bold'))
    
    def load_file(self, filepath):
        """Load and display a text file.
        
        Args:
            filepath: Path to text file
        """
        self.current_file = Path(filepath)
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Update label
            self.file_label.config(text=f'File: {self.current_file.name}')
            self.window.title(f'Text Viewer - {self.current_file.name}')
            
            # Clear and insert text
            self.text.config(state=tk.NORMAL)
            self.text.delete('1.0', tk.END)
            self.text.insert('1.0', content)
            
            # Apply basic syntax highlighting
            self._apply_highlighting()
            
            # Make read-only again
            self.text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.text.config(state=tk.NORMAL)
            self.text.delete('1.0', tk.END)
            self.text.insert('1.0', f'Error loading file:\n{e}')
            self.text.config(state=tk.DISABLED)
    
    def reload(self):
        """Reload the current file."""
        if self.current_file:
            self.load_file(self.current_file)
    
    def _apply_highlighting(self):
        """Apply basic syntax highlighting to the text."""
        content = self.text.get('1.0', tk.END)
        lines = content.split('\n')
        
        for i, line in enumerate(lines, start=1):
            line_start = f'{i}.0'
            
            # Highlight comments (lines starting with # or !)
            if line.strip().startswith('#') or line.strip().startswith('!'):
                self.text.tag_add('comment', line_start, f'{i}.end')
            
            # Highlight section headers (all caps words or lines with =)
            elif '=' in line and len(line.strip().split()) <= 3:
                self.text.tag_add('header', line_start, f'{i}.end')
            elif line.strip() and line.strip().isupper():
                self.text.tag_add('header', line_start, f'{i}.end')
            
            # Highlight numbers
            else:
                words = line.split()
                col = 0
                for word in words:
                    col = line.find(word, col)
                    if col >= 0:
                        try:
                            float(word)
                            start_idx = f'{i}.{col}'
                            end_idx = f'{i}.{col + len(word)}'
                            self.text.tag_add('number', start_idx, end_idx)
                        except ValueError:
                            pass
                        col += len(word)
    
    def close(self):
        """Close the viewer window."""
        self.window.destroy()
    
    def show(self):
        """Show the viewer window."""
        self.window.deiconify()
        self.window.lift()
