import sys
import socket
import threading
import time
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QLineEdit, QTextEdit
from PyQt6.QtCore import pyqtSignal, QObject
import pygame
import keyboard

SOUND_FILE = "zbuff01.wav"

class NetworkHandler(QObject):
    message_received = pyqtSignal(str)
    connection_status = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.sock = None
        self.socket_lock = threading.Lock()

    @property
    def is_running(self):
        """ Computed property for conn status. Socket is the source of truth"""
        return self.sock is not None

    def connect(self, host, port, party, password, username):
        if self.is_running:
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            
            with self.socket_lock:
                self.sock = sock

            self.send(f"JOIN:{party}:{password}:{username}\n")
            threading.Thread(target=self._listen, daemon=True).start()
            self.connection_status.emit(True, "Connected successfully.")
        except Exception as e:
            self.sock = None
            self.connection_status.emit(False, f"Connection error: {e}")

    def _listen(self):
        error_msg = "Connection lost."
        try:
            with self.sock.makefile('r') as f:
                for message in f:
                    self.message_received.emit(message.strip())
        except (OSError, ConnectionAbortedError, ConnectionResetError):
            error_msg = f"Connection closed: {e}"
        except Exception as e:
            error_msg = f"Network error: {e}"
        finally:
            with self.socket_lock:
                self.sock = None
            self.connection_status.emit(False, error_msg)

    def send(self, message):
        with self.socket_lock:
            if self.is_running:
                try:
                    self.sock.sendall(message.encode())
                except OSError:
                    pass # Thread should capture this and handle the disconnect.

    def disconnect(self):
        with self.socket_lock:
            if self.is_running:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass # _listen() finally should handle cleanup.

class ClientApp(QWidget):
    def __init__(self):
        super().__init__()

        #State
        self.is_leader = False
        self.is_connected = False
        self.party_members = []
        
        #Audio
        self._init_audio()
        self._init_network_handler()
        self.init_ui()
        self._init_hotkey()

    def _init_audio(self):
        """Audio Setup"""
        try:
            pygame.mixer.init()
            self.alarm_sound = pygame.mixer.Sound(SOUND_FILE)
        except pygame.error as e:
            self.alarm_sound = None
            self.setup_error(f"Audio error: {e}")

    def _init_network_handler(self):
        """Network Setup"""
        self.network = NetworkHandler()
        self.network.message_received.connect(self.handle_server_message)
        self.network.connection_status.connect(self.handle_connection_status)

    def init_ui(self):
        """UI Setup"""
        self.setWindowTitle('Olun Sync')
        layout = QVBoxLayout()

        self.username_input = QLineEdit("Username")
        self.ip_input = QLineEdit("127.0.0.1")
        self.port_input = QLineEdit("8888")
        self.party_input = QLineEdit("secretolunparty")
        self.password_input = QLineEdit("secret")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_connection)

        self.send_event_button = QPushButton("Send Event")
        self.send_event_button.clicked.connect(self.trigger_start_by_hotkey)

        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)

        layout.addWidget(QLabel("Username:"))
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel("Server IP:"))
        layout.addWidget(self.ip_input)
        layout.addWidget(QLabel("Port:"))
        layout.addWidget(self.port_input)
        layout.addWidget(QLabel("Party Name:"))
        layout.addWidget(self.party_input)
        layout.addWidget(QLabel("Password:"))
        layout.addWidget(self.password_input)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.send_event_button)
        layout.addWidget(QLabel("Status Log:"))
        layout.addWidget(self.status_log)
        self.setLayout(layout)

    def handle_connection_status(self, is_connected, message):
        """Handle connection status signals"""
        self.is_connected = is_connected
        self.log_status(message)
        if not is_connected:
            self.is_leader = False
            self.party_members = []
        self._update_ui_state()

    def handle_server_message(self, msg):
        """ Server Message Parser and Update State"""
        parts = msg.split(":", 1)
        command = parts[0]
        payload = parts[1] if len(parts) > 1 else ""

        if command == "JOIN_OK":
            self.log_status("Successfully joined party!")
        elif command == "PARTY_UPDATE":
            self._parse_party_update(payload)
        elif command == "COUNTDOWN":
            self.log_status("Leader has started the countdown!")
        elif command == "PLAY_SOUND":
            self.log_status("Z-Buff now!")
            if self.alarm_sound:
                self.alarm_sound.play()
        elif command == "TIMER_ALREADY_ACTIVE":
            self.log_status("Timer is already active!")
        elif command == "NOT_LEADER":
            self.log_status("You are not the party leader!")

    def _parse_party_update(self, payload):
        """Parse party updates"""
        self.party_members = payload.split(',') if payload else []
        my_username = self.username_input.text()
        self.is_leader = bool(self.party_members and self.party_members[0] == my_username)

        if not self.party_members:
            self.log_status("Party is now empty.")
        else:
            formatted = [f"{m} (Leader)" if i == 0 else m for i, m in enumerate(self.party_members)]
            self.log_status(f"Party Update ({len(self.party_members)}): {', '.join(formatted)}")
            self._update_ui_state()

    def _update_ui_state(self):
        """Update UI state"""
        self.connect_button.setText("Disconnect" if self.is_connected else "Connect")
        for widget in [self.username_input, self.ip_input, self.port_input, self.party_input, self.password_input]:
            widget.setEnabled(not self.is_connected)

    def _init_hotkey(self):
        try:
            keyboard.add_hotkey('page down', self.trigger_start_by_hotkey)
            self.log_status("Hotkey 'page down' registered to start timer.")
        except Exception as e:
            self.log_status(f"Warning: Could not register hotkey. May need admin rights. {e}")

    def trigger_start_by_hotkey(self):
        if self.is_connected:
            self.network.send("START\n")

    def toggle_connection(self):
        """Handles connnect/disconnect button"""
        if self.network.is_running:
            self.network.disconnect()
        else:
            username = self.username_input.text()
            host = self.ip_input.text()
            port = int(self.port_input.text())
            party = self.party_input.text()
            password = self.password_input.text()
            self.network.connect(host, port, party, password, username)

    def log_status(self, text):
        self.status_log.append(text)

    def update_connection_status(self, is_connected):
        self.connect_button.setText("Disconnect" if is_connected else "Connect")
        for widget in [self.username_input, self.ip_input, self.port_input, self.party_input, self.password_input]:
            widget.setEnabled(not is_connected)
        if not is_connected:
            self.is_leader = False
            self.log_status("Disconnected.")
            
    def closeEvent(self, event):
        self.network.disconnect()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClientApp()
    window.show()
    sys.exit(app.exec())