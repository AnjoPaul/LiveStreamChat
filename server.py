import socket
import threading
import sqlite3
import struct
from flask import Flask, render_template, request, redirect, url_for
from database import *
from chat_server import *
from authenticate import *

app = Flask(__name__)

# In-memory data storage
streams = {}
clients = {}  # To track connected clients

def update_participants(streamer_name):
    """
    Update the list of participants for a stream and notify clients.
    """
    participant_list = list(streams[streamer_name]['clients'].keys())
    
    # Send the updated list of participants to all clients connected to the stream
    for client_sock, client_name in streams[streamer_name]['clients'].items():
        try:
            participant_message = f"{participant_list}"
            client_sock.sendall(participant_message.encode())
        except Exception as e:
            print(f"Error sending participant update: {e}")

# Handle streamer connection
def handle_streamer_connection(sock, streamer_name):
    """
    Handles the incoming video frames from the streamer and broadcasts to clients.
    """
    streams[streamer_name] = {'socket': sock, 'clients': {}}
    print(f"Streamer {streamer_name} connected")

    while True:
        try:
            # Receive frame size (first 8 bytes)
            frame_size_data = sock.recv(8)
            if not frame_size_data:
                print(f"Streamer {streamer_name} stopped streaming")
                break

            frame_size = struct.unpack('>Q', frame_size_data)[0]

            if frame_size > 10**6:  # 1 MB size limit
                print(f"Frame size too large: {frame_size}")
                continue  # Skip this frame

            # Receive the actual frame
            frame_data = b''
            bytes_received = 0
            while bytes_received < frame_size:
                chunk = sock.recv(min(frame_size - bytes_received, 4096))
                if not chunk:
                    break
                frame_data += chunk
                bytes_received += len(chunk)

            # Broadcast the frame to all clients connected to this stream
            for client_sock in streams[streamer_name]['clients'].values():
                try:
                    client_sock.sendall(frame_size_data + frame_data)
                except Exception as e:
                    print(f"Error sending frame to client: {e}")

        except Exception as e:
            print(f"Error in streaming for {streamer_name}: {e}")
            break

    del streams[streamer_name]
    sock.close()

# Handle client connection
def handle_client_connection(sock, client_name, streamer_name):
    """
    Manages the connection for clients, allowing them to receive video frames.
    """
    print(f"Client {client_name} connecting to streamer {streamer_name}")

    if streamer_name in streams:
        streams[streamer_name]['clients'][client_name] = sock
        update_participants(streamer_name)
        print(f"Client {client_name} connected to streamer {streamer_name}")

        while True:
            try:
                # Keep the connection alive
                sock.recv(1024)
            except Exception as e:
                print(f"Error receiving data from client {client_name}: {e}")
                break

        del streams[streamer_name]['clients'][client_name]
        update_participants(streamer_name)
        sock.close()
    else:
        print(f"Streamer {streamer_name} not found for client {client_name}")
        sock.close()

# Chat server handler
def handle_chat_connection(sock, client_name, streamer_name):
    """
    Handles chat messages between clients and streamers.
    """
    print(f"Client {client_name} connected to chat for streamer {streamer_name}")
    clients[sock] = client_name  # Track connected clients

    while True:
        try:
            message = sock.recv(1024).decode()
            if not message:
                break

            # Broadcast the message to all clients of the streamer
            broadcast_message(message, streamer_name, sender=client_name)

        except Exception as e:
            print(f"Error in chat for {client_name}: {e}")
            break

    del clients[sock]
    sock.close()

def broadcast_message(message, streamer_name, sender):
    """
    Broadcast chat messages to all clients connected to the stream.
    """
    formatted_message = f"{sender}: {message}"
    for client_sock in streams[streamer_name]['clients'].values():
        try:
            client_sock.sendall(formatted_message.encode())
        except Exception as e:
            print(f"Error sending chat message: {e}")

# Start TCP server for video and chat
def start_tcp_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', 8001))
    server_socket.listen(5)

    print("TCP server started on port 8001")

    while True:
        client_socket, addr = server_socket.accept()
        data = client_socket.recv(1024).decode()

        if data.startswith('STREAMER:'):
            streamer_name = data.split(':')[1]
            print(f"New streamer connection from {addr}")
            threading.Thread(target=handle_streamer_connection, args=(client_socket, streamer_name)).start()
        elif data.startswith('CLIENT:'):
            client_name, streamer_name = data.split(':')[1], data.split(':')[2]
            print(f"New client connection from {addr}")
            threading.Thread(target=handle_client_connection, args=(client_socket, client_name, streamer_name)).start()

# Start chat server
def start_chat_server():
    chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    chat_socket.bind(('0.0.0.0', 8002))
    chat_socket.listen(5)

    print("Chat server started on port 8002")

    while True:
        client_socket, addr = chat_socket.accept()
        data = client_socket.recv(1024).decode()
        client_name, streamer_name = data.split(':')[1], data.split(':')[2]
        print(f"New chat connection from {addr}")
        threading.Thread(target=handle_chat_connection, args=(client_socket, client_name, streamer_name)).start()

# Route to display participants and allow adding new members
@app.route('/', methods=['GET', 'POST'])
def server_ui():
    conn = sqlite3.connect('streams.db')
    c = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']

        c.execute("SELECT * FROM member WHERE name = ?", (name,))
        if c.fetchone() is None:
            c.execute("INSERT INTO member (name, password) VALUES (?, ?)", (name, password))
            conn.commit()

    c.execute("SELECT name, password FROM member")
    members = c.fetchall()
    conn.close()

    return render_template('server.html', members=members)

# Route to delete a member
@app.route('/delete_member', methods=['POST'])
def delete_member():
    name = request.form['name']

    conn = sqlite3.connect('streams.db')
    c = conn.cursor()

    # Delete the member from the database
    c.execute("DELETE FROM member WHERE name = ?", (name,))
    conn.commit()

    conn.close()

    # Redirect back to the main page to show the updated list
    return redirect(url_for('server_ui'))


# Start all the servers
def start_server():
    threading.Thread(target=start_tcp_server).start()
    threading.Thread(target=start_chat_server).start()
    app.run(debug=True, port=5000, host='0.0.0.0')

if __name__ == "__main__":
    setup_db()
    start_server()
