import sqlite3
import threading
import socket

clients = {}
poll_data={}

# Handle chat connection
# Handle chat connection
def handle_chat_connection(sock, streamer_name, client_name):
    global poll_data  # Access the global poll data
    clients[sock] = streamer_name  # Track which client is connected
    print(f"[Chat] Client {client_name} connected to chat for streamer: {streamer_name}")

    # Send previous chat messages to the new client
    previous_messages = get_chat_for_streamer(streamer_name)

    for name, message in previous_messages:
        sock.sendall(f"{name}: {message}\n".encode())

    while True:
        try:
            message = sock.recv(1024).decode()
            if not message:
                break

            if message.startswith("-POLL-"):
                # Handle the poll message
                poll_options = eval(message.replace("-POLL-", "").strip())
                
                # Initialize poll data for the streamer
                poll_data[streamer_name] = {i + 1: 0 for i in range(len(poll_options))}  # Initialize votes to 0

                # Create a new poll broadcast message
                poll_broadcast_message = f"-NEWPOLL-{poll_options}"

                # Create the initial vote count broadcast message (-RESPOLL-) in dictionary format
                poll_vote_message = {str(i + 1): 0 for i in range(len(poll_options))}  # Option number as key, vote count as value

                # Broadcast the poll and the initial vote counts (dictionary format) to all clients in the stream
                for client_sock, streamer in clients.items():
                    if streamer == streamer_name:
                        client_sock.sendall(f"{poll_broadcast_message}\n".encode())
                        client_sock.sendall(f"-RESPOLL-{poll_vote_message}\n".encode())

            elif message.startswith("-VOTE-"):
                # Handle voting
                option_number = int(message.replace("-VOTE-", "").strip())
                
                # Check if the poll exists for the streamer and if the option number is valid
                if streamer_name in poll_data and option_number in poll_data[streamer_name]:
                    # Increment the vote for the selected option
                    poll_data[streamer_name][option_number] += 1
                    print(f"[Vote] {client_name} voted for option {option_number}")

                    # Broadcast the updated poll results to all clients
                    updated_poll_message = {str(option): count for option, count in poll_data[streamer_name].items()}
                    for client_sock, streamer in clients.items():
                        if streamer == streamer_name:
                            client_sock.sendall(f"-RESPOLL-{updated_poll_message}\n".encode())
                else:
                    print(f"[Vote] Invalid vote option received from {client_name}")

            else:
                # Handle regular chat message
                clean_message = message.replace(f"{client_name}: ", "")
                save_chat_message(streamer_name, client_name, clean_message)

                # Broadcast the regular message to all clients
                for client_sock, streamer in clients.items():
                    if streamer == streamer_name or client_sock == sock:  # Include the streamer in the broadcast
                        client_sock.sendall(f"{client_name}: {clean_message}\n".encode())

        except Exception as e:
            print(f"[Chat] Error: {e}")
            break


    del clients[sock]
    sock.close()

def start_chat_server():
    chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    chat_socket.bind(('0.0.0.0', 8002))
    chat_socket.listen(5)

    print("[Chat Server] Started on port 8002")

    while True:
        client_socket, _ = chat_socket.accept()
        data = client_socket.recv(1024).decode()
        if data.startswith('CLIENT:'):
            _, client_name, streamer_name = data.split(':')
            print(f"[Chat Server] Client {client_name} connected to streamer {streamer_name}")
            threading.Thread(target=handle_chat_connection, args=(client_socket, streamer_name, client_name)).start()
        elif data.startswith('STREAMER:'):
            _, client_name, streamer_name = data.split(':')
            print(f"[Chat Server] Streamer {client_name} connected to streamer chat {streamer_name}")
            clear_chat_for_streamer(streamer_name)
            threading.Thread(target=handle_chat_connection, args=(client_socket, streamer_name, client_name)).start()

# Clear chat messages for a specific streamer
def clear_chat_for_streamer(streamer_name):
    conn = sqlite3.connect('streams.db')
    c = conn.cursor()
    c.execute("DELETE FROM chat WHERE streamer_name = ?", (streamer_name,))
    conn.commit()
    conn.close()


# Save chat message to the database
def save_chat_message(streamer_name, client_name, message):
    conn = sqlite3.connect('streams.db')
    c = conn.cursor()
    c.execute("INSERT INTO chat (streamer_name, client_name, message) VALUES (?, ?, ?)",
              (streamer_name, client_name, message))
    conn.commit()
    conn.close()

# Fetch chat messages for a specific streamer
def get_chat_for_streamer(streamer_name):
    conn = sqlite3.connect('streams.db')
    c = conn.cursor()
    c.execute("SELECT client_name, message FROM chat WHERE streamer_name = ?", (streamer_name,))
    chat_messages = c.fetchall()
    conn.close()
    return chat_messages


