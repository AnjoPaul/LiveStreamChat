import socket
import sqlite3
import threading

def handle_authentication(sock):
    try:
        # Receive username and password
        credentials = sock.recv(1024).decode().split(':')
        if len(credentials) != 2:
            sock.sendall("INVALID:Invalid format\n".encode())
            sock.close()
            return

        username, password = credentials

        # Check credentials in the database
        conn = sqlite3.connect('streams.db')
        c = conn.cursor()
        c.execute("SELECT * FROM member WHERE name = ? AND password = ?", (username, password))
        if c.fetchone():
            sock.sendall("VALID:Welcome\n".encode())
        else:
            sock.sendall("INVALID:Invalid username or password\n".encode())
        
        conn.close()
    except Exception as e:
        print(f"[Auth Error] {e}")
    finally:
        sock.close()

def start_auth_server():
    auth_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    auth_socket.bind(('0.0.0.0', 8003))
    auth_socket.listen(5)

    print("[Auth Server] Started on port 8003")

    while True:
        client_socket, _ = auth_socket.accept()
        threading.Thread(target=handle_authentication, args=(client_socket,)).start()