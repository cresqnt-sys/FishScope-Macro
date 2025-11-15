import requests 
import json 
import webbrowser 
from PyQt6 .QtWidgets import QMessageBox ,QDialog ,QVBoxLayout ,QHBoxLayout ,QPushButton ,QLabel 
from PyQt6 .QtCore import Qt ,QThread ,pyqtSignal 
from PyQt6 .QtGui import QFont 
import sys 
import os 
from packaging .version import parse as parse_version 
CURRENT_VERSION ='2.4-Beta2'

class UpdateChecker (QThread ):
    update_available =pyqtSignal (str ,str )
    no_update =pyqtSignal ()
    error_occurred =pyqtSignal (str )

    def run (self ):
        try :
            response =requests .get ('https://api.github.com/repos/cresqnt-sys/FishScope-Macro/releases/latest',timeout =10 )
            if response .status_code ==200 :
                release_data =response .json ()
                latest_version =release_data .get ('tag_name','').lstrip ('v')
                download_url =release_data .get ('html_url','')
                if self .is_newer_version (latest_version ,CURRENT_VERSION ):
                    self .update_available .emit (latest_version ,download_url )
                else :
                    self .no_update .emit ()
            else :
                self .error_occurred .emit (f'Failed to check for updates: HTTP {response .status_code }')
        except requests .exceptions .RequestException as e :
            self .error_occurred .emit (f'Network error while checking for updates: {str (e )}')
        except Exception as e :
            self .error_occurred .emit (f'Error checking for updates: {str (e )}')

    def is_newer_version (self ,latest ,current ):
        try :

            return parse_version (latest )>parse_version (current )
        except Exception :

            try :
                def numeric_parts (v ):
                    base =v .split ('-')[0 ]
                    return [int (x )for x in base .split ('.')]
                latest_parts =numeric_parts (latest )
                current_parts =numeric_parts (current )
                max_len =max (len (latest_parts ),len (current_parts ))
                latest_parts .extend ([0 ]*(max_len -len (latest_parts )))
                current_parts .extend ([0 ]*(max_len -len (current_parts )))
                return latest_parts >current_parts 
            except Exception :
                return False 

class UpdateDialog (QDialog ):

    def __init__ (self ,latest_version ,download_url ,parent =None ):
        super ().__init__ (parent )
        self .download_url =download_url 
        self .setup_ui (latest_version )

    def setup_ui (self ,latest_version ):
        self .setWindowTitle ('Update Available')
        self .setFixedSize (450 ,200 )
        self .setModal (True )
        self .setStyleSheet ("\n            QDialog {\n                background-color: #2d2d2d;\n                color: #e0e0e0;\n                font-family: 'Segoe UI', Arial, sans-serif;\n            }\n            QLabel {\n                color: #e0e0e0;\n                background-color: transparent;\n            }\n            QPushButton {\n                background-color: #4a4a4a;\n                color: #e0e0e0;\n                border: 1px solid #666666;\n                padding: 8px 16px;\n                border-radius: 6px;\n                font-weight: 500;\n                font-size: 13px;\n                min-width: 80px;\n            }\n            QPushButton:hover {\n                background-color: #5a5a5a;\n                border-color: #777777;\n            }\n            QPushButton:pressed {\n                background-color: #3a3a3a;\n                border-color: #888888;\n            }\n            QPushButton#update_btn {\n                background-color: #28a745;\n                border-color: #28a745;\n            }\n            QPushButton#update_btn:hover {\n                background-color: #218838;\n                border-color: #218838;\n            }\n            QPushButton#update_btn:pressed {\n                background-color: #1e7e34;\n                border-color: #1e7e34;\n            }\n        ")
        layout =QVBoxLayout (self )
        layout .setSpacing (16 )
        layout .setContentsMargins (20 ,20 ,20 ,20 )
        title_label =QLabel ('Update Available')
        title_font =QFont ('Segoe UI',16 ,QFont .Weight .Bold )
        title_label .setFont (title_font )
        title_label .setAlignment (Qt .AlignmentFlag .AlignCenter )
        layout .addWidget (title_label )
        message =f'A new version of FishScope Macro is available!\n\nCurrent version: {CURRENT_VERSION }\nLatest version: {latest_version }\n\nWould you like to download the update?'
        message_label =QLabel (message )
        message_label .setFont (QFont ('Segoe UI',11 ))
        message_label .setAlignment (Qt .AlignmentFlag .AlignCenter )
        message_label .setWordWrap (True )
        layout .addWidget (message_label )
        button_layout =QHBoxLayout ()
        button_layout .setSpacing (12 )
        later_btn =QPushButton ('Later')
        later_btn .clicked .connect (self .reject )
        button_layout .addWidget (later_btn )
        update_btn =QPushButton ('Download Update')
        update_btn .setObjectName ('update_btn')
        update_btn .clicked .connect (self .download_update )
        button_layout .addWidget (update_btn )
        layout .addLayout (button_layout )

    def download_update (self ):
        webbrowser .open (self .download_url )
        self .accept ()

class AutoUpdater :

    def __init__ (self ,parent_widget =None ):
        self .parent_widget =parent_widget 
        self .update_checker =None 

    def check_for_updates (self ,silent =False ):
        if self .update_checker and self .update_checker .isRunning ():
            return 
        self .silent =silent 
        self .update_checker =UpdateChecker ()
        self .update_checker .update_available .connect (self .on_update_available )
        self .update_checker .no_update .connect (self .on_no_update )
        self .update_checker .error_occurred .connect (self .on_error )
        self .update_checker .start ()

    def on_update_available (self ,latest_version ,download_url ):
        dialog =UpdateDialog (latest_version ,download_url ,self .parent_widget )
        dialog .exec ()

    def on_no_update (self ):
        if not self .silent :
            msg =QMessageBox (self .parent_widget )
            msg .setWindowTitle ('No Updates')
            msg .setText ('You are running the latest version of FishScope Macro.')
            msg .setIcon (QMessageBox .Icon .Information )
            msg .setStyleSheet ('\n                QMessageBox {\n                    background-color: #2d2d2d;\n                    color: white;\n                }\n                QMessageBox QPushButton {\n                    background-color: #4a4a4a;\n                    color: white;\n                    border: 1px solid #666666;\n                    padding: 8px 16px;\n                    border-radius: 4px;\n                    min-width: 80px;\n                }\n                QMessageBox QPushButton:hover {\n                    background-color: #5a5a5a;\n                }\n            ')
            msg .exec ()

    def on_error (self ,error_message ):
        if not self .silent :
            msg =QMessageBox (self .parent_widget )
            msg .setWindowTitle ('Update Check Failed')
            msg .setText (f'Failed to check for updates:\n{error_message }')
            msg .setIcon (QMessageBox .Icon .Warning )
            msg .setStyleSheet ('\n                QMessageBox {\n                    background-color: #2d2d2d;\n                    color: white;\n                }\n                QMessageBox QPushButton {\n                    background-color: #4a4a4a;\n                    color: white;\n                    border: 1px solid #666666;\n                    padding: 8px 16px;\n                    border-radius: 4px;\n                    min-width: 80px;\n                }\n                QMessageBox QPushButton:hover {\n                    background-color: #5a5a5a;\n                }\n            ')
            msg .exec ()

    def get_current_version (self ):
        return CURRENT_VERSION 