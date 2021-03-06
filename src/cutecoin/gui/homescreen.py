"""
Created on 31 janv. 2015

@author: vit
"""

from PyQt5.QtWidgets import QWidget
from ..gen_resources.homescreen_uic import Ui_HomeScreenWidget
from ..__init__ import __version__
from . import toast


class HomeScreenWidget(QWidget, Ui_HomeScreenWidget):
    """
    classdocs
    """

    def __init__(self, app):
        """
        Constructor
        """
        super().__init__()
        self.setupUi(self)
        self.app = app
        self.refresh_text()
        self.app.version_requested.connect(self.refresh_text)

    def refresh_text(self):
        latest = self.app.available_version
        version_info = ""
        version_url = ""
        if not latest[0]:
            version_info = self.tr("Please get the latest release {version}") \
                            .format(version=latest[1])
            version_url = latest[2]

        self.label_welcome.setText(
            self.tr("""
            <h1>Welcome to Cutecoin {version}</h1>
            <h2>{version_info}</h2>
            <h3><a href={version_url}>Download link</a></h3>
            """).format(version=latest[1],
                       version_info=version_info,
                       version_url=version_url))

