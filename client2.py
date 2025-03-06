from flask import Flask, render_template, Response, request, jsonify, redirect, url_for
import socket
import struct
import logging
import threading

app = Flask(__name__)

streamer_name = None
client_name = None
chat_socket = None  # Define chat_socket at a global level
messages_list = []  # Global list to store chat messages
participants = []
poll_options = None
poll_data = None
has_voted = False  # Global variable to track if the client has voted

Ip_aadr = '192.168.15.117'

# Maximum frame size in bytes
MAX_FRAME_SIZE = 10 * 1024 * 1024  # 10 MB

# Configure logging
logging.basicConfig(level=logging.INFO)

# Function to authenticate with the server on port 8003
def authenticate(username, password):
    auth_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        print("Trying to connect to 8003")
        auth_socket.connect((Ip_aadr, 8003))
        print("succesfully connected to 8003")
        auth_socket.sendall(f"{username}:{password}".encode())
        print("Sent to 8003")
        response = auth_socket.recv(1024).decode()
        return response
    except socket.error as e:
        logging.error(f"Socket error: {e}")
        return "ERROR:Connection error"
    except Exception as e:
        logging.error(f"Error: {e}")
        return "ERROR:Unknown error occurred"
    finally:
        auth_socket.close()

# Fetch video frames from server
def fetch_video_frames():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((Ip_aadr, 8001))  # Local IP for server
        client_socket.sendall(f'CLIENT:{client_name}:{streamer_name}'.encode())

        payload_size = struct.calcsize('>Q')  # Size of frame length header (8 bytes)
        data = b''

        while True:
            try:
                while len(data) < payload_size:
                    packet = client_socket.recv(4096)
                    if not packet:
                        logging.warning("No frame size data received, stopping stream")
                        return
                    data += packet

                frame_size_data = data[:payload_size]
                data = data[payload_size:]
                frame_size = struct.unpack('>Q', frame_size_data)[0]

                if frame_size > MAX_FRAME_SIZE:
                    logging.warning(f"Received frame too large: {frame_size} bytes, skipping frame.")
                    continue

                while len(data) < frame_size:
                    packet = client_socket.recv(4096)
                    if not packet:
                        logging.warning("No more frame data received, stopping stream")
                        return
                    data += packet

                frame_data = data[:frame_size]
                data = data[frame_size:]

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')

            except Exception as e:
                logging.error(f"Error receiving video frames: {e}")
                break

    finally:
        client_socket.close()

@app.route('/')
def client_ui():
    return render_template('client_login.html')  # Show login page

@app.route('/search')
def search():
    return render_template('client_search.html')  # Show search page after login

@app.route('/login', methods=['POST'])
def login():
    global client_name
    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        return jsonify({"status": "error", "message": "Username or password not provided"})

    response = authenticate(username, password)
    
    if response.startswith("VALID"):
        client_name = username
        # Redirect to the search page after successful login
        return redirect(url_for('search'))
    elif response.startswith("INVALID"):
        return jsonify({"status": "error", "message": "Invalid username or password"})
    else:
        return jsonify({"status": "error", "message": response})

@app.route('/video_feed')
def video_feed():
    return Response(fetch_video_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/join_stream', methods=['POST'])
def join_stream():
    global client_name, streamer_name, chat_socket  # Make chat_socket global
    streamer_name = request.form.get('streamer_name')

    # Start chat listener thread
    chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    chat_socket.connect((Ip_aadr, 8002))
    chat_socket.sendall(f'CLIENT:{client_name}:{streamer_name}'.encode())
    threading.Thread(target=chat_listener, daemon=True).start()

    return render_template('client_stream.html', client_name=client_name, streamer_name=streamer_name)

def chat_listener():
    global participants, poll_data, poll_options, has_voted
    print(f"[Chat Listener] Connected to chat server on port 8002")

    while True:
        try:
            message = chat_socket.recv(1024).decode()
            if message:
                if message.startswith("["):
                    participants = [streamer_name] + message.strip("[]").replace("'", "").split(",")

                elif message.startswith("-NEWPOLL-"):
                    poll_options = message.replace("-NEWPOLL-", "").strip()
                    poll_options = poll_options.strip("[]").replace("'", "").split(",")
                    has_voted = False  # Reset voting status when a new poll is received
                    print(f"[Chat Listener] New Poll received: {poll_options}")

                elif message.startswith("-RESPOLL-"):  # Handling poll results
                    results = message.replace("-RESPOLL-", "").strip()
                    poll_data = eval(results)  # Store poll results
                    print(f"[Chat Listener] Poll results received: {poll_data}")

                else:
                    print(f"[Chat Listener] Message received: {message}")
                    messages_list.append(message)  # Store message in global list

            else:
                break
        except Exception as e:
            print(f"[Chat Listener] Error receiving message: {e}")
            break

@app.route('/send_message', methods=['POST'])
def send_message():
    global chat_socket
    message = request.form.get('message')
    if message:
        print(f"[Client] Sending message: {message}")
        chat_socket.sendall(f"{client_name}: {message}".encode())
        print(f"[Client] Message sent: {message}")
    else:
        print("[Client] No message to send")
    return '', 204  # No content response

@app.route('/get_participants', methods=['GET'])
def get_participants():
    return jsonify(participants), 200  # Return the list of participants as JSON

@app.route('/get_poll_results', methods=['GET'])
def get_poll_results():
    global poll_data
    if isinstance(poll_data, dict):  # Check if poll_data is a dictionary containing results
        return jsonify(poll_data), 200  # Return the poll results as JSON
    else:
        return jsonify({"message": "No poll results available"}), 200  # Return message if no results

@app.route('/get_poll', methods=['GET'])
def get_poll():
    global poll_options  # Use poll_options instead of poll_data
    if poll_options:
        return jsonify(poll_options), 200  # Return the poll options directly
    else:
        return jsonify({"message": "No active poll at the moment"}), 200  # Return message if no poll

@app.route('/vote/<int:option>', methods=['POST'])
def vote(option):
    global chat_socket, has_voted

    if has_voted:
        # If the client has already voted, return an alert message
        return jsonify({"alert": "Already Given Vote"}), 400

    # If the client has not voted yet
    vote_message = f"-VOTE-{option}"
    chat_socket.sendall(vote_message.encode())
    has_voted = True  # Set has_voted to True after voting
    print(f"[Client] Vote sent: {vote_message}")
    
    return '', 204  # Success response with no content

@app.route('/get_messages', methods=['GET'])
def get_messages():
    return jsonify(messages_list), 200  # Return the list of messages as JSON

def start_client():
    app.run(debug=True, port=5003)

if __name__ == '__main__':
    start_client()
