import asyncio
import time

HOST = '0.0.0.0'
PORT = 8888
COUNTDOWN_SECONDS = 275

parties = {}

class Party:
    def __init__(self, name, password):
        self.name = name
        self.password = password
        self.members = []
        self.leader = None
        self.timer_task = None

    async def broadcast(self, message, exclude_writer=None):
        """Sends a message to all members of the party."""
        print(f"[PARTY: {self.name}] Broadcasting: {message}")
        for reader, writer, _ in self.members:
            if writer is not exclude_writer:
                try:
                    writer.write(message.encode())
                    await writer.drain()
                except ConnectionResetError:
                    pass

    async def start_countdown(self):
        """Starting the Z-Buff timer."""
        await self.broadcast("SERVER_MSG: Leader has started the countdown!")
        await asyncio.sleep(COUNTDOWN_SECONDS)
        await self.broadcast("PLAY_SOUND\n")

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"New connection from {addr}")
    
    current_party = None
    client_username = None
    
    try:
        data = await reader.readline()
        if not data:
            return
        
        message = data.decode().strip()
        
        if not message.startswith("JOIN:"):
            writer.write("JOIN_FAIL: Invalid command. Must join a party first.\n".encode())
            await writer.drain()
            return

        try:
            _, party_name, password, username = message.split(":", 3)
            client_username = username
        except ValueError:
            writer.write("JOIN_FAIL: Invalid JOIN format. Use JOIN:party:pass:user\n").encode()
            await writer.drain()
            return
        
        if party_name not in parties:
            parties[party_name] = Party(party_name, password)
            print(f"Created new party: {party_name}")

        party = parties[party_name]
        current_party = party

        if party.password != password:
            writer.write("JOIN_FAIL: Incorrect password.\n".encode())
            await writer.drain()
            return
            
        party.members.append((reader, writer, username))
        if party.leader is None:
            party.leader = writer

        writer.write("JOIN_OK\n".encode())
        await writer.drain()

        member_list = ",".join([uname for r, w, uname in party.members])
        await party.broadcast(f"MEMBERS: {member_list}\n")

        while True:
            data = await reader.readline()
            if not data:
                break
                
            command = data.decode().strip()
            print(f"Received from {addr}: {command}")

            if command == "PING":
                writer.write("PONG\n".encode())
                await writer.drain()
            
            elif command == "START" and writer == party.leader:
                if party.timer_task and not party.timer_task.done():
                    print(f"Party '{party.name}' timer is already running.")
                    writer.write("SERVER_MSG: Timer is already active.\n".encode())
                else:
                    party.timer_task = asyncio.create_task(party.start_countdown())
            
            elif command == "START" and writer != party.leader:
                writer.write("SERVER_MSG: Only the party leader can start the timer.\n".encode())
                await writer.drain()

    except (ConnectionResetError, asyncio.IncompleteReadError):
        print(f"Client {client_username}@{addr} disconnected unexpectedly.") 
    finally:
        if current_party and client_username:
            member_to_remove = next((m for m in current_party.members if m[1] is writer), None)
            if member_to_remove:
                current_party.members.remove(member_to_remove)
                print(f"Client {client_username}@{addr} removed from party '{current_party.name}'")

            if current_party.leader is writer and current_party.members:
                new_leader_writer = current_party.members[0][1]
                new_leader_username = current_party.members[0][2]
                current_party.leader = new_leader_writer
                await current_party.broadcast(f"SERVER_MSG: Leader has left. New leader is {new_leader_username}@{new_leader_writer.get_extra_info('peername')[0]}\n")

            member_list = ",".join([uname for r, w, uname in current_party.members])
            await current_party.broadcast(f"MEMBERS: {member_list}\n")
            
            if not current_party:
                print(f"Party '{current_party.name}' is now empty. Deleting.")
                del parties[current_party.name]

        writer.close()
        await writer.wait_closed()
        print(f"Connection with {client_username}@{addr} closed.")


async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    print(f"Server started on {HOST}:{PORT}")
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())