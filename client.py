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
    connection_status = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.sock = None
        self.is_running = False
        self.socket_lock = threading.Lock()

    def connect(self, host, port, party, password):
        self.is_running = True
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self.send(f"JOIN:{party}:{password}\n")
            threading.Thread(target=self.listen, daemon=True).start()
            self.connection_status.emit(True)
        except Exception as e:
            self.message_received.emit(f"Connection Error: {e}")
            self.connection_status.emit(False)

    def listen(self):
        try:
            f = self.sock.makefile()
            while self.is_running:
                try:
                    message = f.readline().strip()
                    if not message:
                        break
                    self.message_received.emit(message)
                except (OSError, ConnectionAbortedError, ConnectionResetError):
                    self.message_received.emit("Connection closed by client exception.")
                except Exception as e:
                    self.message_received.emit(f"Network error: {e}")
        finally:
            self.is_running = False
            self.connection_status.emit(False)

    def send(self, message):
        if self.sock and self.is_running:
            self.sock.sendall(message.encode())

    def disconnect(self):
        if not self.is_running:
            return
        
        self.is_running = False
        if self.socket_lock:
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            self.sock.close()
            self.sock = None
        self.connection_status.emit(False)


class ClientApp(QWidget):
    def __init__(self):
        super().__init__()
        self.is_leader = False
        
        pygame.mixer.init()
        self.alarm_sound = pygame.mixer.Sound(SOUND_FILE)
        
        self.network = NetworkHandler()
        self.network.message_received.connect(self.handle_server_message)
        self.network.connection_status.connect(self.update_connection_status)
        
        self.init_ui()
        self.init_hotkey()

    def init_ui(self):
        self.setWindowTitle('Olun Sync')
        layout = QVBoxLayout()

        self.ip_input = QLineEdit("127.0.0.1")
        self.port_input = QLineEdit("8888")
        self.party_input = QLineEdit("secretolunparty")
        self.password_input = QLineEdit("secret")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_connection)

        self.ping_button = QPushButton("Test (Ping Server)")
        self.ping_button.clicked.connect(lambda: self.network.send("PING\n"))
        self.ping_button.setEnabled(False)

        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)

        layout.addWidget(QLabel("Server IP:"))
        layout.addWidget(self.ip_input)
        layout.addWidget(QLabel("Port:"))
        layout.addWidget(self.port_input)
        layout.addWidget(QLabel("Party Name:"))
        layout.addWidget(self.party_input)
        layout.addWidget(QLabel("Password:"))
        layout.addWidget(self.password_input)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.ping_button)
        layout.addWidget(QLabel("Status Log:"))
        layout.addWidget(self.status_log)
        self.setLayout(layout)

    def init_hotkey(self):
        try:
            keyboard.add_hotkey('page down', self.trigger_start_by_hotkey)
            self.log_status("Hotkey 'page down' registered to start timer.")
        except Exception as e:
            self.log_status(f"Warning: Could not register hotkey. May need admin rights. {e}")

    def trigger_start_by_hotkey(self):
        if self.is_leader:
            self.log_status("Hotkey triggered! Sending START command as leader.")
            self.network.send("START\n")
        else:
            self.log_status("Hotkey triggered, but you are not the leader.")

    def toggle_connection(self):
        if self.network.is_running:
            self.network.disconnect()
        else:
            self.connect_button.setText("Connecting...")
            host = self.ip_input.text()
            port = int(self.port_input.text())
            party = self.party_input.text()
            password = self.password_input.text()
            self.network.connect(host, port, party, password)

    def log_status(self, text):
        self.status_log.append(text)

    def update_connection_status(self, is_connected):
        self.ping_button.setEnabled(is_connected)
        self.connect_button.setText("Disconnect" if is_connected else "Connect")
        for widget in [self.ip_input, self.port_input, self.party_input, self.password_input]:
            widget.setEnabled(not is_connected)
        if not is_connected:
            self.is_leader = False
            self.log_status("Disconnected.")

    def handle_server_message(self, msg):
        if msg == "JOIN_OK":
            self.log_status("Successfully joined party!")
        elif msg.startswith("NEW_MEMBER:"):
            _, members_str = msg.split(":", 1)
            members = members_str.split(',')
            my_ip = self.network.sock.getsockname()[0]
            if members and (members[0] == my_ip or members[0] == '127.0.0.1'):
                self.is_leader = True
                self.log_status("You are the party leader!")
            else:
                self.is_leader = False
                self.log_status("You are a party member.")
        elif msg == "PLAY_SOUND":
            self.log_status("!!! RECEIVED PLAY COMMAND. Z-BUFF NOW. !!!")
            self.alarm_sound.play()
            
    def closeEvent(self, event):
        self.network.disconnect()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClientApp()
    window.show()
    sys.exit(app.exec())