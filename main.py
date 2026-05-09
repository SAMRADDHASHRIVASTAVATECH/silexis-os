"""
CENTRAL SYSTEM INTERFACE — Entry Point
Run this file to launch the full system.
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.main_window import MainWindow


def main():
    window = MainWindow()
    window.run()


if __name__ == "__main__":
    main()
