import cv2
import numpy as np
import socket
import struct
import threading
import time
from flask import Flask, render_template, Response, redirect, url_for, request, jsonify

app = Flask(__name__)

video_capture = cv2.VideoCapture(0)
streaming_active = True
streamer_name = None
chat_socket = None
messages_list = []
participants = []
poll_data = None

Ip_aadr = '10.12.234.228'

total_frames_sent = 0
total_frames_expected = 0
start_time = time.time()
latency_data = []
packet_loss_data = []
bandwidth = 0

# Stream video to the server
def stream_video_to_server(streamer_socket):
    global total_frames_sent, total_frames_expected, start_time, latency_data, packet_loss_data, bandwidth

    frame_rate = 30
    frame_time = 1 / frame_rate
    total_data_received = 0
    while streaming_active:
        ret, frame = video_capture.read()
        if not ret:
            print("Error: Couldn't capture frame")
            break

        total_frames_expected += 1

        capture_time = time.time()
        _, frame_data = cv2.imencode('.jpg', frame)
        frame_data = frame_data.tobytes()
        frame_size = len(frame_data)
        try:
            streamer_socket.sendall(struct.pack('>Q', frame_size) + frame_data)
            total_frames_sent += 1
            elapsed_time = time.time() - start_time

            total_data_received += frame_size
            bandwidth = total_data_received / elapsed_time if elapsed_time > 0 else 0

            latency = time.time() - capture_time
            latency_data.append(latency)

            packet_loss = ((total_frames_expected - total_frames_sent) / total_frames_expected) * 100
            packet_loss_data.append(packet_loss)

            print(f"[Streamer] Bandwidth: {bandwidth:.2f} bytes/sec, Latency: {latency:.2f} sec, Packet Loss: {packet_loss:.2f}%")

            time.sleep(frame_time)

        except Exception as e:
            print(f"Error sending video frame: {e}")
            break
    video_capture.release()
    streamer_socket.close()

def compute_streamer_performance():
    avg_bandwidth = round(bandwidth) if bandwidth else 0
    avg_latency = round(np.mean(latency_data) * 1000, 3) if latency_data else 0
    max_latency = round(np.max(latency_data) * 1000, 3) if latency_data else 0
    min_latency = round(np.min(latency_data) * 1000, 3) if latency_data else 0
    avg_packet_loss = round(np.mean(packet_loss_data), 3) if packet_loss_data else 0

    return {
        "Average Bandwidth (bytes/sec)": avg_bandwidth,
        "Average Latency (ms)": avg_latency,
        "Max Latency (ms)": max_latency,
        "Min Latency (ms)": min_latency,
        "Average Packet Loss (%)": avg_packet_loss,
        "Total Frames Sent": total_frames_sent,
        "Total Frames Expected": total_frames_expected,
    }

@app.route('/streamer_performance')
def streamer_performance():
    performance_data = compute_streamer_performance()
    return jsonify(performance_data), 200

@app.route('/')
def streamer_entry():
    return render_template('streamer_entry.html')

@app.route('/login', methods=['POST'])
def login():
    global streamer_name
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        return jsonify({"status": "error", "message": "Username or password not provided"})

    response = authenticate(username, password)
    
    if response.startswith("VALID"):
        streamer_name = username
        return redirect(url_for('streamer_streaming'))
    elif response.startswith("INVALID"):
        return jsonify({"status": "error", "message": "Invalid username or password"})
    else:
        return jsonify({"status": "error", "message": response})

@app.route('/start_stream', methods=['POST'])
def start_stream():
    global streamer_name, chat_socket
    streamer_name = request.form.get('streamer_name')

    streamer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    streamer_socket.connect((Ip_aadr, 8001))  # Connect to video server
    streamer_socket.sendall(f'STREAMER:{streamer_name}'.encode())

    chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    chat_socket.connect((Ip_aadr, 8002))  # Connect to chat server
    chat_socket.sendall(f'STREAMER:{streamer_name}:{streamer_name}'.encode())
    threading.Thread(target=chat_listener, daemon=True).start()

    threading.Thread(target=stream_video_to_server, args=(streamer_socket,)).start()

    return redirect(url_for('streamer_streaming'))

@app.route('/streaming')
def streamer_streaming():
    if not streamer_name:
        return redirect(url_for('streamer_entry'))
    return render_template('streamer_streaming.html', streamer_name=streamer_name)

@app.route('/video_feed')
def video_feed():
    return Response(stream_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

def stream_video():
    while True:
        ret, frame = video_capture.read()
        if not ret:
            break
        _, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/end_stream', methods=['POST'])
def end_stream():
    global streaming_active
    streaming_active = False
    return redirect(url_for('streamer_entry'))

def chat_listener():
    global participants, poll_data
    print(f"[Chat Listener] Connected to chat server on port 8002")

    while True:
        try:
            message = chat_socket.recv(1024).decode()
            if message:
                if message.startswith("["):
                    participants = [streamer_name] + message.strip("[]").replace("'", "").split(",")

                elif message.startswith("-NEWPOLL-"):
                    continue
                elif message.startswith("-RESPOLL-"):
                    results = message.replace("-RESPOLL-", "").strip()
                    poll_data = eval(results)
                    print(f"[Chat Listener] Poll results received: {poll_data}")

                else:
                    print(f"[Chat Listener] Message received: {message}")
                    messages_list.append(message)

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
        print(f"[Server] Sending message: {message}")
        chat_socket.sendall(f"{streamer_name}: {message}".encode())
        print(f"[Server] Message sent: {message}")
    return '', 204

@app.route('/send_poll', methods=['POST'])
def send_poll():
    global chat_socket
    poll_options = request.form.getlist('poll_options[]')
    if len(poll_options) >= 2 and len(poll_options) <= 4:
        poll_message = f"-POLL-{poll_options}"
        chat_socket.sendall(f"{poll_message}".encode())
        print(f"[Server] Poll sent: {poll_message}")
    return '', 204

@app.route('/get_participants', methods=['GET'])
def get_participants():
    return jsonify(participants), 200

@app.route('/get_poll_results', methods=['GET'])
def get_poll_results():
    global poll_data
    if isinstance(poll_data, dict):
        return jsonify(poll_data), 200
    else:
        return jsonify({"message": "No poll results available"}), 200

@app.route('/get_messages', methods=['GET'])
def get_messages():
    return jsonify(messages_list), 200

def authenticate(username, password):
    auth_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        auth_socket.connect((Ip_aadr, 8003))
        auth_socket.sendall(f"{username}:{password}".encode())
        response = auth_socket.recv(1024).decode()
        return response
    except socket.error as e:
        return "ERROR:Connection error"
    except Exception as e:
        return "ERROR:Unknown error occurred"
    finally:
        auth_socket.close()

def start_streamer():
    app.run(host='0.0.0.0', port=5002, debug=True)

if __name__ == '__main__':
    start_streamer()
