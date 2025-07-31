import sys
import asyncio
import threading
import time
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QLineEdit, QTextEdit
from PyQt6.QtCore import pyqtSignal, QObject
import pygame
import keyboard
import websockets

SOUND_FILE = "zbuff01.wav"

class NetworkHandler(QObject):
    message_received = pyqtSignal(str)
    connection_status = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.websocket = None
        self.is_running = False
        self.uri = ""

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_async_loop, daemon=True)
        self.thread.start()

    def run_async_loop(self):
        """Runs the async loop in a thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def connect(self, host, port, party, password, username):
        if self.is_running:
            return
        self.uri = f"ws://{host}:{port}"

        asyncio.run_coroutine_threadsafe(
            self._connect(party, password, username),
            self.loop
        )

    async def _connect(self, party, password, username):
        try:
            async with websockets.connect(self.uri) as websocket:
                self.websocket = websocket
                self.is_running = True
                self.connection_status.emit(True, "Connected successfully.")

                await self.websocket.send(f"JOIN:{party}:{password}:{username}")

                async for message in self.websocket:
                    self.message_received.emit(message)

        except (websockets.exceptions.ConnectionClose, ConnectionRefusedError) as e:
            self.connection_status.emit(False, f"Connection closed: {e}")
        except Exception as e:
            self.connection_status.emit(False, f"Connection error: {e}")
        finally:
            self.is_running = False
            self.websocket = None
            self.connection_status.emit(False, "Disconnected.")

    def send(self, message):
        if self.is_running and self.websocket:
            asyncio.run_coroutine_threadsafe(
                self.websocket.send(message),
                self.loop
            )

    def disconnect(self):
        if self.is_running and self.websocket:
            asyncio.run_coroutine_threadsafe(
                self.websocket.close(),
                self.loop
            )

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

        match command:
            case "JOIN_OK":
                self.log_status("Successfully joined party!")
            case "PARTY_UPDATE":
                self._parse_party_update(payload)
            case "COUNTDOWN":
                self.log_status("Leader has started the countdown!")
            case "PLAY_SOUND":
                self.log_status("Z-Buff now!")
                if self.alarm_sound:
                    self.alarm_sound.play()
            case "TIMER_ALREADY_ACTIVE":
                self.log_status("Timer is already active!")
            case "NOT_LEADER":
                self.log_status("You are not the party leader!")
            case "INVALID_COMMAND":
                self.log_status("Invalid command. Use JOIN:party:pass:user")
            case "INVALID_JOIN_FORMAT":
                self.log_status("Invalid JOIN format. Use JOIN:party:pass:user")
            case "INCORRECT_PASSWORD":
                self.log_status("Incorrect password.")
        
    def _parse_party_update(self, payload):
        """Parse party updates"""
        active_party, *self.party_members = payload.split(':')
        my_username = self.username_input.text()
        self.is_leader = bool(self.party_members and self.party_members[0] == my_username)

        if not self.party_members:
            self.log_status("Party is now empty.")
        else:
            output_message = f"[{active_party}]({len(self.party_members)}): {', '.join(self.party_members)}"
            self.log_status(output_message)
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
            self.network.send("START")

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