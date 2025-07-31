import asyncio
import argparse
import websockets
import time

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
        print(f"[INFO]: '{username}' joined party '{self.name}'.")
        if self.leader_websocket is None:
            self.leader_websocket = websocket
            print(f"[INFO]: '{username}' is the new leader of party '{self.name}'.")
        await self._broadcast_party_update()
    
    async def remove_member(self, websocket):
        """Removes member and handle leader promotion if needed."""
        member_to_remove = self.get_member_by_websocket(websocket)
        if not member_to_remove:
            return # not found?!?

        leaving_username = member_to_remove[1]
        self.members.remove(member_to_remove)
        print(f"[INFO]: '{leaving_username}' left party '{self.name}'.")

        # Promote leader?!
        if self.leader_websocket is websocket:
            if self.members:
                self.leader_websocket = self.members[0][0]
                new_leader_username = self.members[0][1]
                print(f"[INFO]: '{new_leader_username}' is the new leader of party '{self.name}'.")
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
        message = f"PARTY_UPDATE:{','.join(member_list)}"
        print(f"[PARTY - {self.name}]: Broadcasting Update: {message.strip()}")
        await self.broadcast(message)

    async def start_countdown(self):
        """Timer and broadcast events from countdown."""
        print(f"[PARTY - {self.name}]: Starting countdown.")
        await self.broadcast("COUNTDOWN")
        await asyncio.sleep(COUNTDOWN_SECONDS)
        print(f"[PARTY - {self.name}]: Countdown complete. Playing sound.")
        await self.broadcast("PLAY_SOUND")

class Server:
    """Encapsulates the server logic."""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.parties = {}

    async def handle_client(self, websocket):
        """Handles a single client connection."""
        addr = websocket.remote_address
        print(f"[INFO]: New conn - {addr}")
        
        party = None
        username = None
        
        try:
            join_message = await websocket.recv()

            if not join_message.startswith("JOIN:"):
                print(f"[ERROR]: '{command}' - '{username}' in '{party_name}': INVALID_COMMAND")
                await websocket.send("JOIN_FAIL: Invalid command. Use JOIN command.")
                return

            try:
                _, party_name, password, username = join_message.split(":", 3)
            except ValueError:
                print(f"[ERROR]: '{command}' - '{username}' in '{party_name}': INVALID_JOIN_FORMAT")
                websocket.send("JOIN_FAIL: Invalid JOIN format. Use JOIN:party:pass:user")
                return
            
            if party_name not in self.parties:
                self.parties[party_name] = Party(party_name, password)
                print(f"[INFO]: New party created: {party_name}")

            party = self.parties[party_name]

            if party.password != password:
                print(f"[ERROR]: '{command}' - '{username}' in '{party_name}': INCORRECT_PASSWORD")
                websocket.send("JOIN_FAIL: Incorrect password.")
                party = None
                return
            
            await websocket.send("JOIN_OK")
            await party.add_member(websocket, username)

            # Main command loop
            async for command in websocket:
                print(f"[INFO]: '{username}' in '{party_name}': '{command}'")

                if command == "START":
                    if party.leader_websocket is websocket:
                        if party.timer_task and not party.timer_task.done():
                            print(f"[ERROR]: '{command}' - '{username}' in '{party_name}': TIMER_ALREADY_ACTIVE")
                            await websocket.send("TIMER_ALREADY_ACTIVE: Timer is already active.")
                        else:
                            print(f"[INFO]: '{command}' - '{username}' in '{party_name}': TIMER_STARTED")
                            party.timer_task = asyncio.create_task(party.start_countdown())
                    else:
                        print(f"[ERROR]: '{command}' - '{username}' in '{party_name}': NOT_LEADER")
                        await websocket.send("NOT_LEADER: Only party leader can start the timer.")
        except websockets.exceptions.ConnectionClosed:
            print(f"[INFO]: Client disconnected - {username}@{addr}.")
        except Exception as e:
            print(f"[ERROR]: Unexpected error for {username}@{addr}: {e.with_traceback()}")
        finally:
            if party:
                is_empty = await party.remove_member(websocket)
                if is_empty:
                    print(f"[INFO]: Party '{party.name}' is now empty. Deleting.")
                    if party.name in self.parties:
                        del self.parties[party.name]
            print(f"[INFO]: Closed conn handler - {username}@{addr}.")
    
    async def start(self):
        """Starts the server."""
        async with websockets.serve(self.handle_client, self.host, self.port):
            print(f"[DEBUG]: WebSocket at ws://{self.host}:{self.port}")
            await asyncio.Future()

async def main():
    """Parse args and run server"""
    parser = argparse.ArgumentParser(description="BDO Dist Timer Server")
    parser.add_argument("--port", type=int, default=8888, help="Server port")
    parser.add_argument("--host", default="0.0.0.0", help="Server IP")
    args = parser.parse_args()

    server_instance = Server(host=args.host, port=args.port)
    await server_instance.start()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO]: Server shutting down.")