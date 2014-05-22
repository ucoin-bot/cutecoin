'''
Created on 22 mai 2014

@author: inso
'''
import re
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QProgressDialog
from PyQt5.QtCore import QThread, pyqtSignal

from cutecoin.models.person import Person

from cutecoin.gen_resources.generateKeyDialog_uic import Ui_GenerateKeyDialog



class TaskGenKey(QThread):
    taskFinished = pyqtSignal()

    def run(self):
        self.key = self.account.gpg.gen_key(self.input_data)
        self.taskFinished.emit()

class GenerateKeyDialog(QDialog, Ui_GenerateKeyDialog):

    '''
    classdocs
    '''

    def __init__(self, account, parent=None):
        '''
        Constructor
        '''
        super(GenerateKeyDialog, self).__init__()
        self.setupUi(self)
        self.account = account
        self.main_window = parent
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)

    def accept(self):
        name = self.edit_name.text()
        passphrase = self.edit_password.text()
        input_data = self.account.gpg.gen_key_input(key_type="RSA", key_length=2048,
                                 name_real=name, passphrase=passphrase)

        self.progress_dialog = QProgressDialog(self)
        self.progress_dialog.setLabelText("Generating key...")
        self.progress_dialog.setMinimum(0)
        self.progress_dialog.setMaximum(0)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setValue(-1) # As set in Designer
        self.progress_dialog.show()
        self.gen_task = TaskGenKey()
        self.gen_task.input_data = input_data
        self.gen_task.account = self.account
        self.gen_task.taskFinished.connect(self.gen_finished)
        self.gen_task.run()

    def gen_finished(self):
        self.progress_dialog.close()
        if self.account.keyid is not '':
            self.account.gpg.delete_keys(self.account.keyid)

        key = self.gen_task.key
        secret_keys = self.account.gpg.list_keys(True)
        for k in secret_keys:
            if k['fingerprint'] == key.fingerprint:
                self.account.keyid = k['keyid']

        print(self.account.keyid)

        QMessageBox.information(self, "Key generation", "Key " +
                                key.fingerprint + " has been generated",
                        QMessageBox.Ok)
        self.main_window.label_fingerprint.setText("Key : " + key.fingerprint)
        self.main_window.button_next.setEnabled(True)
        self.close()

    def check(self):
        if len(self.edit_password.text()) < 8:
            self.label_errors.setText("Please enter a password with more than 8 characters")
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
            return
        elif self.edit_password.text() != self.edit_password_bis.text():
            self.label_errors.setText("Passphrases do not match")
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
            return
        else:
            pattern = re.compile("([A-Za-z-.]+ )([A-Za-z-.]+( )*)+")
            if not pattern.match(self.edit_name.text()):
                self.label_errors.setText("Please enter your name and family name.")
                self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
                return

        self.label_errors.setText("")
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)

