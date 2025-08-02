import asyncio
import argparse
import websockets
import logging
import os
import sys
import ssl

COUNTDOWN_SECONDS = 5

class Party:
    """Representas a single party. Manages its own members and timer state."""
    def __init__(self, name, password):
        self.name = name
        self.password = password
        self.members = []
        self.leader_websocket = None
        self.timer_task = None

    def get_member_list(self):
        """Return list of usernames for members of the party."""
        return [uname for _, uname in self.members]
    
    def get_member_by_websocket(self, websocket):
        """Return username of member with given websocket connection."""
        return next((m for m in self.members if m[0] is websocket), None)

    async def add_member(self, websocket, username):
        """Adds new member and broadcasts event."""
        if self.get_member_by_websocket(websocket): return
        self.members.append((websocket, username))
        logging.info(f"[{self.name}]: JOIN_PARTY_OK - '{username}'")
        if self.leader_websocket is None:
            self.leader_websocket = websocket
            logging.info(f"[{self.name}]: LEADER_PROMOTION - '{username}'")
        await self._broadcast_party_update()
    
    async def remove_member(self, websocket):
        """Removes member and handle leader promotion if needed."""
        member_to_remove = self.get_member_by_websocket(websocket)
        if not member_to_remove:
            return # not found?!?

        leaving_username = member_to_remove[1]
        self.members.remove(member_to_remove)
        logging.info(f"[{self.name}]: '{leaving_username}' left.")

        # Promote leader?!
        if self.leader_websocket is websocket:
            if self.members:
                self.leader_websocket = self.members[0][0]
                new_leader_username = self.members[0][1]
                logging.info(f"[{self.name}]: LEADER_PROMOTION - '{new_leader_username}'")
            else:
                # empty party here
                self.leader_websocket = None
        await self._broadcast_party_update()
        return not self.members

    async def broadcast(self, message, exclude_websocket=None):
        """Sends a message to all members of the party."""
        websockets_to_send = [ws for ws, _ in self.members if ws is not exclude_websocket]
        if websockets_to_send:
            websockets.broadcast(websockets_to_send, message)

    async def _broadcast_party_update(self):
        """Helper to handle party update broadcasts."""
        member_list = self.get_member_list()
        message = f"PARTY_UPDATE:{self.name}:{':'.join(member_list)}"  
        logging.info(f"[{self.name}]: PARTY_UPDATE - {", ".join(member_list)}")
        await self.broadcast(message)

    async def start_countdown(self):
        """Timer and broadcast events from countdown."""
        logging.info(f"[{self.name}]: Starting countdown. Broadcasting COUNTDOWN.")
        await self.broadcast("COUNTDOWN")
        await asyncio.sleep(COUNTDOWN_SECONDS)
        logging.info(f"[{self.name}]: Countdown complete. Broadcasting PLAY_SOUND.")
        await self.broadcast("PLAY_SOUND")

class Server:
    """Encapsulates the server logic."""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.parties = {}

    async def handle_client(self, websocket):
        """Client connection Lifecycle"""
        addr = websocket.remote_address
        logging.info(f"[NEW_CONN] - {addr}")
        party, username = None, None

        try:
            party, username = await self._handle_join_request(websocket)
            if not party:
                return # On join fail, should already have responded.
            await self._process_commands(websocket, party, username)
        except websockets.exceptions.ConnectionClosed:
            logging.error(f"[CONNECTION_CLOSED] - {username}@{addr}.")
        except Exception as e:
            logging.error(f"[UNEXPECTED_ERROR] - {username}@{addr}: {e}")
        finally:
            if party and websocket:
                if await party.remove_member(websocket):
                    logging.info(f"[{party.name}] PARTY_EMPTY - CLEANUP START.")
                    del self.parties[party.name]
            logging.info(f"[CONNECTION_CLOSED] - {username}@{addr}.")

    async def _handle_join_request(self, websocket):
        """ Waits, parses and validate initial 'JOIN:'. Return (party, username) or (None, None)"""
        try:
            join_message = await websocket.recv()
        except websockets.exceptions.ConnectionClosed:
            logging.error(f"[CONNECTION_CLOSED] - {websocket}")
            return None, None
        
        if not join_message.startswith("JOIN:"):
            await self._send_error(websocket, "INVALID_COMMAND")
            return None, None
        
        try:
            _, party_name, password, username  = join_message.split(":", 3)
        except ValueError:
            await self._send_error(websocket, "INVALID_JOIN_FORMAT", party_name, username)
            return None, None
        
        if not party_name and len(party_name.strip()) < 1:
            await self._send_error(websocket, "INVALID_PARTY_NAMING", party_name, username)
            return None, None

        if party_name not in self.parties:
            self.parties[party_name] = Party(party_name, password)
            logging.info(f"[{party_name}]: CREATE_PARTY")
        
        party = self.parties[party_name]

        if party.password != password:
            await self._send_error(websocket, "INCORRECT_PASSWORD", party_name, username)
            return None, None

        await websocket.send("JOIN_OK")
        logging.info(f"[{party_name}]: JOIN_OK - {username}'")
        await party.add_member(websocket, username)

        return party, username

    async def _process_commands(self, websocket, party, username):
        """Proccess incoming commands and routes it."""
        async for command in websocket:
            if command == "START":
                await self._handle_start_command(websocket, party, username)
            elif command == "CLOSE_CONN":
                try:
                    logging.info(f"[{party.name}]: CLOSE_CONN - {username}")
                except websockets.exceptions.ConnectionClosed:
                    pass
                break # Cleanup at finally block
            else:
                await self._send_error(websocket, "UNKNOWN_COMMAND", party, username)
                return
    
    async def _handle_start_command(self, websocket, party, username):
        """Olun 275s Timer start command"""
        if party.leader_websocket is not websocket:
            await self._send_error(websocket, "NOT_LEADER", party.name, username)
            return
        if party.timer_task and not party.timer_task.done():
            await self._send_error(websocket, "TIMER_ALREADY_ACTIVE", party.name, username)
            return
        logging.info(f"[{party.name}]: START - '{username}'")
        party.timer_task = asyncio.create_task(party.start_countdown())

    async def _send_error(self, websocket, error_code, party_name, username):
        """Sends error_code to Client"""
        try:
            await websocket.send(error_code)
            logging.error(f"[{party_name}]: {error_code} - '{username}'")
        except websockets.exceptions.ConnectionClosed:
            pass # Client disconnected before receiving?

    async def start(self):
        """Starts the server."""
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cert_path = resource_path('cert.pem')
        key_path = resource_path('key.pem')
        
        try:
            ssl_context.load_cert_chain(cert_path, key_path)
            logging.info(f"[CERT]: SSL Certificate loaded successfully from {cert_path}")
        except FileNotFoundError:
            logging.error(f"[CERT]: SSL Certificate files ('cert.pem', 'key.pem') not found.")
            
        async with websockets.serve(self.handle_client, self.host, self.port, ssl=ssl_context):
            logging.info(f"[WEBSOCKET]: wss://{self.host}:{self.port}")
            await asyncio.Future()

def resource_path(relative_path):
    """ Get absolute path to resource"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def logging_setup():
    """Init Logging config."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

async def main():
    """Parse args and run server"""
    parser = argparse.ArgumentParser(description="BDO Dist Timer Server")
    parser.add_argument("--port", type=int, default=8888, help="Server port")
    parser.add_argument("--host", default="0.0.0.0", help="Server IP")
    args = parser.parse_args()
    logging_setup()

    server_instance = Server(host=args.host, port=args.port)
    await server_instance.start()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.debug("Shutting down.")