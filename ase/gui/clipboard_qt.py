from ase import Atoms
from ase.io.jsonio import decode, encode
from PyQt5.QtWidgets import QApplication


class AtomsClipboard:
    def __init__(self, tk=None):
        # tk parameter kept for API compatibility but not used
        pass

    def get_text(self) -> str:
        clipboard = QApplication.clipboard()
        return clipboard.text()

    def set_text(self, text: str) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def get_atoms(self) -> Atoms:
        text = self.get_text()
        atoms = decode(text)
        if not isinstance(atoms, Atoms):
            typename = type(atoms).__name__
            raise ValueError(f'Cannot convert {typename} to Atoms')
        return atoms

    def set_atoms(self, atoms: Atoms) -> None:
        json_text = encode(atoms)
        self.set_text(json_text)
