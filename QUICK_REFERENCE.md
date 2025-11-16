# ASE-GUI Workspace Mode - Quick Reference

## Installation
No installation needed - works with existing ASE installation!

## Launch Commands

```bash
# Workspace mode (directory)
python -m ase.gui /path/to/directory
python -m ase.gui .                    # Current directory

# Normal mode (files) - unchanged
python -m ase.gui structure.cif
python -m ase.gui POSCAR CONTCAR
python -m ase.gui *.xyz
```

## File Type Icons

| Icon | Type | Opens In |
|------|------|----------|
| 📁 | Directory | Expandable in sidebar |
| ⚛️ | Structure (POSCAR, CIF, XYZ) | Atomic viewer |
| 🎬 | Trajectory (XDATCAR, .traj) | Trajectory player |
| 📊 | Volumetric (CHGCAR, LOCPOT) | Structure + info |
| 📝 | Text (INCAR, KPOINTS) | Text viewer window |
| 📄 | Other | Auto-detect or error |

## Navigation

| Action | Result |
|--------|--------|
| Click file | Select and open |
| Double-click folder | Expand/collapse |
| Click ↻ button | Refresh file tree |

## Features

✅ File explorer sidebar (resizable)
✅ Automatic file type detection
✅ Multiple text viewers
✅ Structure/trajectory loading
✅ Full backward compatibility

## Keyboard Shortcuts

All existing shortcuts work unchanged:
- Arrow keys: Navigate frames
- +/- : Zoom in/out
- Ctrl+O : Open file dialog
- Etc.

## Quick Demo

```bash
# Run interactive demo
python demo_workspace_mode.py
```

## File Support

**Structure Files:**
POSCAR, CONTCAR, CIF, XYZ, PDB, MOL, SDF, GEN, CAR

**Trajectory Files:**
XDATCAR, .traj, .nc, .dcd, .xtc, .trr

**Volumetric Files:**
CHGCAR, LOCPOT, CHG, ELFCAR, AECCAR*

**Text Files:**
INCAR, KPOINTS, POTCAR, OUTCAR, DOSCAR, EIGENVAL

## Common Workflows

### View VASP Calculation
```bash
cd vasp_run/
python -m ase.gui .
# Click POSCAR → view initial
# Click CONTCAR → view final
# Click XDATCAR → play trajectory
# Click INCAR → check parameters
```

### Browse Structure Database
```bash
python -m ase.gui ~/structures/
# Navigate folders
# Click any structure to view
```

## Troubleshooting

**Q: No sidebar appears**
A: Make sure you're opening a directory, not a file

**Q: File doesn't open**
A: Check file format is supported, check error dialog

**Q: Want old behavior**
A: Just open files instead of directory - unchanged!

## Documentation

- Full User Guide: `WORKSPACE_MODE_README.md`
- Technical Docs: `IMPLEMENTATION_SUMMARY.md`
- Complete Overview: `WORKSPACE_COMPLETE.md`

## Contact

For issues or questions, refer to ASE documentation at:
https://wiki.fysik.dtu.dk/ase/

---
**Quick Start:** `python -m ase.gui .` in any directory!
