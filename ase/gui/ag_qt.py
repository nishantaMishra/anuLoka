# fmt: off

"""
Qt-based ASE-GUI Entry Point.

This is an alternative entry point that uses PyQt5 instead of Tkinter.
Run with: python -m ase.gui.ag_qt [files...]
"""

import os
import sys
import warnings

# Force Qt backend for matplotlib before any other imports
import matplotlib
matplotlib.use('Qt5Agg')


class CLICommand:
    """ASE's graphical user interface (Qt Version).

    ASE-GUI Qt.  See the online manual
    (https://ase-lib.org/ase/gui/gui.html)
    for more information.
    """

    @staticmethod
    def add_arguments(parser):
        add = parser.add_argument
        add('filenames', nargs='*',
            help='Files to open.  Append @SLICE to a filename to pick '
            'a subset of images from that file.  See --image-number '
            'for SLICE syntax.')
        add('-n', '--image-number', metavar='SLICE', default=':',
            help='Pick individual image or slice from each of the files.  '
            'SLICE can be a number or a Python slice-like expression '
            'such as :STOP, START:STOP, or START:STOP:STEP, '
            'where START, STOP, and STEP are integers.  '
            'Indexing counts from 0.  '
            'Negative numbers count backwards from last image.  '
            'Using @SLICE syntax for a filename overrides this option '
            'for that file.')
        add('-r', '--repeat',
            default='1',
            help='Repeat unit cell.  Use "-r 2" or "-r 2,3,1".')
        add('-R', '--rotations', default='',
            help='Examples: "-R -90x", "-R 90z,-30x".')
        add('-o', '--output', metavar='FILE',
            help='Write configurations to FILE.')
        add('-g', '--graph',
            metavar='EXPR',
            help='Plot x,y1,y2,... graph from configurations or '
            'write data to sdtout in terminal mode.')
        add('-t', '--terminal',
            action='store_true',
            default=False,
            help='Run in terminal window - no GUI.')
        add('--interpolate',
            type=int, metavar='N',
            help='Interpolate N images between 2 given images.')
        add('-b', '--bonds',
            action='store_true',
            default=False,
            help='Draw bonds between atoms.')
        add('-s', '--scale', dest='radii_scale', metavar='FLOAT',
            default=None, type=float,
            help='Scale covalent radii.')

    @staticmethod
    def run(args):
        from pathlib import Path
        from ase.atoms import Atoms
        from ase.gui.images import Images
        from ase.gui.gui_qt import GUI

        # Check if a single directory was provided
        workspace_dir = None
        if len(args.filenames) == 1:
            path = Path(args.filenames[0])
            if path.is_dir():
                workspace_dir = str(path.resolve())
                images = Images()
                images.initialize([Atoms()])
            else:
                images = Images()
                images.read(args.filenames, args.image_number)
        elif args.filenames:
            images = Images()
            images.read(args.filenames, args.image_number)
        else:
            images = Images()
            images.initialize([Atoms()])

        if args.interpolate:
            images.interpolate(args.interpolate)

        if args.repeat != '1':
            r = args.repeat.split(',')
            if len(r) == 1:
                r = 3 * r
            images.repeat_images([int(c) for c in r])

        if args.radii_scale:
            images.scale_radii(args.radii_scale)

        if args.output is not None:
            warnings.warn('You should be using "ase convert ..." instead!')
            images.write(args.output, rotations=args.rotations)
            args.terminal = True

        if args.terminal:
            if args.graph is not None:
                data = images.graph(args.graph)
                for line in data.T:
                    for x in line:
                        print(x, end=' ')
                    print()
        else:
            gui = GUI(images, args.rotations, args.bonds, args.graph,
                     workspace_dir=workspace_dir)
            gui.run()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='ASE GUI (Qt Version)')
    CLICommand.add_arguments(parser)
    args = parser.parse_args()
    CLICommand.run(args)


if __name__ == '__main__':
    main()
