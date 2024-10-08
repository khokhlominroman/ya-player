# -*- coding: utf-8 -*-
"""
The entryu point of YaPlayer.
"""
if __name__ == '__main__':
    import sys
    from os import getcwd, path
    from PyQt5.QtCore import QSize
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QApplication
    from gui import YaPlayerWindow, _APP_TITLE

    app = QApplication(sys.argv)
    app.setApplicationName(_APP_TITLE)
    ic = QIcon()
    ic.addFile(path.join(getcwd(), 'ui', 'images', 'logo.png'), QSize(64, 64))
    app.setWindowIcon(ic)
    _w = YaPlayerWindow()
    _w.show()
    _w.login()
    sys.exit(app.exec_())
