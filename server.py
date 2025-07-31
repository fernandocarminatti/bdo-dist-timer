import asyncio
import time

HOST = '0.0.0.0'
PORT = 8888
COUNTDOWN_SECONDS = 2

parties = {}

class Party:
    def __init__(self, name, password):
        self.name = name
        self.password = password
        self.members = []
        self.leader_writer = None
        self.timer_task = None

    def get_member_list(self):
        """Return list of usernames for members of the party."""
        return [uname for _,_, uname in self.members]
    
    def get_member_by_writer(self, writer):
        """Return username of member with given writer."""
        return next((m for m in self.members if m[1] is writer), None)

    async def add_member(self, reader, writer, username):
        """Adds new member and broadcasts event."""
        if self.get_member_by_writer(writer):
            return
        self.members.append((reader, writer, username))
        print(f"[INFO]: '{username}' joined party '{self.name}'.")
        if self.leader_writer is None:
            self.leader_writer = writer
            print(f"[INFO]: '{username}' is the new leader of party '{self.name}'.")
        await self._broadcast_party_update()
    
    async def remove_member(self, writer):
        """Removes member and handle leader promotion if needed."""
        member_to_remove = self.get_member_by_writer(writer)
        if not member_to_remove:
            return # not found?!?
        
        leaving_username = member_to_remove[2]
        self.members.remove(member_to_remove)
        print(f"[INFO]: '{leaving_username}' left party '{self.name}'.")

        # Promote leader?!
        if self.leader_writer is writer:
            if self.members:
                self.leader_writer = self.members[0][1]
            else:
                # empty party here
                self.leader_writer = None
        await self._broadcast_party_update()
        return not self.members

    async def broadcast(self, message, exclude_writer=None):
        """Sends a message to all members of the party."""
        message_bytes = message.encode()
        for _, writer, _ in self.members:
            if writer is not exclude_writer:
                try:
                    writer.write(message_bytes)
                    await writer.drain()
                except (ConnectionResetError, BrokenPipeError):
                    pass # client likely disconnected ?? Main handle clean this up.

    async def _broadcast_party_update(self):
        """Helper to handle party update broadcasts."""
        member_list = self.get_member_list()
        message = f"PARTY_UPDATE:{','.join(member_list)}\n"
        print(f"[PARTY - {self.name}]: Broadcasting Update: {message.strip()}")
        await self.broadcast(message)

    async def start_countdown(self):
        """Timer and broadcast events from countdown."""
        print(f"[PARTY - {self.name}]: Starting countdown.")
        await self.broadcast("COUNTDOWN\n")
        await asyncio.sleep(COUNTDOWN_SECONDS)
        print(f"[PARTY - {self.name}]: Countdown complete. Playing sound.")
        await self.broadcast("PLAY_SOUND\n")

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"[INFO]: New conn - {addr}")
    
    party = None
    
    try:
        data = await reader.readline()
        if not data: return
        
        message = data.decode().strip()
        if not message.startswith("JOIN:"):
            print(f"[ERROR]: '{command}' - '{username}' in '{party_name}': INVALID_COMMAND")
            writer.write("JOIN_FAIL: Invalid command. Use JOIN:party:pass:user\n".encode())
            await writer.drain()
            return

        try:
            _, party_name, password, username = message.split(":", 3)
        except ValueError:
            print(f"[ERROR]: '{command}' - '{username}' in '{party_name}': INVALID_JOIN_FORMAT")
            writer.write("JOIN_FAIL: Invalid JOIN format. Use JOIN:party:pass:user\n").encode()
            await writer.drain()
            return
        
        if party_name not in parties:
            parties[party_name] = Party(party_name, password)
            print(f"[INFO]: New party created: {party_name}")

        party = parties[party_name]

        if party.password != password:
            print(f"[ERROR]: '{command}' - '{username}' in '{party_name}': INCORRECT_PASSWORD")
            writer.write("JOIN_FAIL: Incorrect password.\n".encode())
            await writer.drain()
            party = None
            return
        
        await party.add_member(reader, writer, username)
        writer.write("JOIN_OK\n".encode())
        await writer.drain()

        # Main command loop
        while True:
            data = await reader.readline()
            if not data: break
                
            command = data.decode().strip()
            print(f"[INFO]: '{username}' in '{party_name}': '{command}'")

            if command == "START":
                if party.leader_writer is writer:
                    if party.timer_task and not party.timer_task.done():
                        print(f"[ERROR]: '{command}' - '{username}' in '{party_name}': TIMER_ALREADY_ACTIVE")
                        writer.write("TIMER_ALREADY_ACTIVE: Timer is already active.\n".encode())
                        await writer.drain()
                    else:
                        print(f"[INFO]: '{command}' - '{username}' in '{party_name}': TIMER_STARTED")
                        party.timer_task = asyncio.create_task(party.start_countdown())
                else:
                    print(f"[ERROR]: '{command}' - '{username}' in '{party_name}': NOT_LEADER")
                    writer.write("NOT_LEADER: Only party leader can start the timer.\n".encode())
                    await writer.drain()
    except (ConnectionResetError, asyncio.IncompleteReadError):
        pass # Client disconnect unexpectedly. Finally handles cleanup.
    finally:
        if party:
            is_empty = await party.remove_member(writer)
            if is_empty:
                print(f"[INFO]: Party '{party.name}' is now empty. Deleting.")
                if party.name in parties:
                    del parties[party.name]
        writer.close()
        await writer.wait_closed()
        print(f"[INFO]: Closed conn - {username}@{addr}.")


async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    print(f"[DEBUG]: Server at {HOST}:{PORT}")
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())