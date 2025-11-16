# fmt: off

"""File type classifier for ASE-GUI workspace mode.

Classifies files by type to route them to appropriate viewers:
- Structure files (POSCAR, CONTCAR, CIF, etc.) -> atomic viewer
- Volumetric files (CHGCAR, LOCPOT, etc.) -> volumetric visualizer
- Trajectory files (XDATCAR, .traj, etc.) -> trajectory player
- Text input files (INCAR, KPOINTS, etc.) -> text viewer
- Other files -> attempt generic handling or show message
"""

import os
from pathlib import Path


class FileType:
    """File type enumeration."""
    STRUCTURE = 'structure'
    TRAJECTORY = 'trajectory'
    VOLUMETRIC = 'volumetric'
    TEXT_INPUT = 'text_input'
    UNKNOWN = 'unknown'


class FileClassifier:
    """Classify files by their type for workspace navigation."""
    
    # VASP structure files
    STRUCTURE_FILES = {
        'POSCAR', 'CONTCAR', 'POSCAR.orig', 'POSCAR.gz', 'CONTCAR.gz'
    }
    
    # Structure file extensions
    STRUCTURE_EXTENSIONS = {
        '.cif', '.xyz', '.pdb', '.mol', '.sdf', '.mol2', 
        '.gen', '.car', '.in', '.struct', '.json'
    }
    
    # VASP volumetric data files
    VOLUMETRIC_FILES = {
        'CHGCAR', 'LOCPOT', 'CHG', 'ELFCAR', 'AECCAR0', 
        'AECCAR1', 'AECCAR2'
    }
    
    # Trajectory files
    TRAJECTORY_FILES = {
        'XDATCAR', 'movie.xyz'
    }
    
    TRAJECTORY_EXTENSIONS = {
        '.traj', '.nc', '.dcd', '.xtc', '.trr'
    }
    
    # VASP text input files
    TEXT_INPUT_FILES = {
        'INCAR', 'KPOINTS', 'POTCAR', 'OUTCAR', 'vasprun.xml',
        'DOSCAR', 'EIGENVAL', 'OSZICAR', 'IBZKPT', 'PCDAT', 
        'XDATCAR', 'ase-sort.dat', 'WAVECAR', 'CHGCAR.gz'
    }
    
    # Generic text input extensions
    TEXT_INPUT_EXTENSIONS = {
        '.in', '.inp', '.txt', '.log', '.out', '.dat', '.xml'
    }
    
    @classmethod
    def classify(cls, filepath):
        """Classify a file by its type.
        
        Args:
            filepath: str or Path object
            
        Returns:
            FileType enum value
        """
        path = Path(filepath)
        filename = path.name
        ext = path.suffix.lower()
        
        # Check structure files by name
        if filename in cls.STRUCTURE_FILES:
            return FileType.STRUCTURE
            
        # Check volumetric files by name
        if filename in cls.VOLUMETRIC_FILES:
            return FileType.VOLUMETRIC
            
        # Check trajectory files by name
        if filename in cls.TRAJECTORY_FILES:
            return FileType.TRAJECTORY
            
        # Check by extension
        if ext in cls.STRUCTURE_EXTENSIONS:
            return FileType.STRUCTURE
            
        if ext in cls.TRAJECTORY_EXTENSIONS:
            return FileType.TRAJECTORY
            
        # Text inputs: check by name first, then extension
        if filename in cls.TEXT_INPUT_FILES:
            return FileType.TEXT_INPUT
            
        if ext in cls.TEXT_INPUT_EXTENSIONS:
            return FileType.TEXT_INPUT
            
        # Try to determine from content if file is small enough
        if path.exists() and path.is_file():
            try:
                size = path.stat().st_size
                # Only try to sniff small files
                if size < 100_000:  # 100 KB
                    return cls._classify_by_content(path)
            except Exception:
                pass
                
        return FileType.UNKNOWN
    
    @classmethod
    def _classify_by_content(cls, path):
        """Try to classify by reading file content.
        
        Args:
            path: Path object
            
        Returns:
            FileType enum value
        """
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                first_lines = [f.readline().strip() for _ in range(10)]
                content = '\n'.join(first_lines)
                
            # Check for common patterns
            if 'data_' in content or '_cell_length' in content:
                # Likely a CIF file
                return FileType.STRUCTURE
                
            if content.count('\n') > 0:
                lines = content.split('\n')
                # Check if it looks like POSCAR format
                if len(lines) >= 3:
                    try:
                        # POSCAR line 2 should be a scaling factor
                        float(lines[1].strip())
                        # POSCAR lines 3-5 should be lattice vectors
                        parts = lines[2].strip().split()
                        if len(parts) == 3:
                            [float(x) for x in parts]
                            return FileType.STRUCTURE
                    except (ValueError, IndexError):
                        pass
                        
        except Exception:
            pass
            
        return FileType.UNKNOWN
    
    @classmethod
    def is_structure_file(cls, filepath):
        """Check if file is a structure file."""
        return cls.classify(filepath) == FileType.STRUCTURE
    
    @classmethod
    def is_volumetric_file(cls, filepath):
        """Check if file is a volumetric data file."""
        return cls.classify(filepath) == FileType.VOLUMETRIC
    
    @classmethod
    def is_trajectory_file(cls, filepath):
        """Check if file is a trajectory file."""
        return cls.classify(filepath) == FileType.TRAJECTORY
    
    @classmethod
    def is_text_input_file(cls, filepath):
        """Check if file is a text input file."""
        return cls.classify(filepath) == FileType.TEXT_INPUT
    
    @classmethod
    def is_readable_by_ase(cls, filepath):
        """Check if file is likely readable by ASE."""
        ftype = cls.classify(filepath)
        return ftype in (FileType.STRUCTURE, FileType.TRAJECTORY)
