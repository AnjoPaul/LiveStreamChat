from flask import Flask, render_template, Response, request, jsonify, redirect, url_for
import socket
import struct
import cv2
import logging
import threading
import time
import matplotlib.pyplot as plt
import numpy as np

app = Flask(__name__)

streamer_name = None
client_name = None
chat_socket = None  
messages_list = [] 
participants = []
poll_options = None
poll_data = None
has_voted = False  

Ip_aadr = '192.168.32.28'

MAX_FRAME_SIZE = 10 * 1024 * 1024  # 10 MB

time_stamps = []
throughput_data = []
latency_data = []
packet_loss_data = []
total_frames_expected = 0
total_frames_received = 0

client_disconnected = False

logging.basicConfig(level=logging.INFO)

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

def fetch_video_frames():
    global time_stamps, throughput_data, latency_data, packet_loss_data, total_frames_expected, total_frames_received, client_disconnected
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((Ip_aadr, 8001))
        client_socket.sendall(f'CLIENT:{client_name}:{streamer_name}'.encode())
        
        payload_size = struct.calcsize('>Q')
        data = b'' 
        total_data_received = 0
        start_time = time.time()
        
        while True:
            try:
               
                total_frames_expected += 1

       
                while len(data) < payload_size:
                    packet = client_socket.recv(4096)
                    if not packet:
                        client_disconnected = True  
                    data += packet

                frame_size_data = data[:payload_size]
                data = data[payload_size:]
                frame_size = struct.unpack('>Q', frame_size_data)[0]

                if frame_size > MAX_FRAME_SIZE:
                    continue

                while len(data) < frame_size:
                    packet = client_socket.recv(4096)
                    if not packet:
                        client_disconnected = True  
                        return
                    data += packet

                frame_data = data[:frame_size]
                data = data[frame_size:]
      
                total_frames_received += 1

                total_data_received += len(frame_data)
                elapsed_time = time.time() - start_time
                throughput = total_data_received / elapsed_time if elapsed_time > 0 else 0

                start_processing_time = time.time()
    
                frame = cv2.imdecode(np.frombuffer(frame_data, np.uint8), cv2.IMREAD_COLOR)
      
                processing_time = time.time() - start_processing_time
                latency_data.append(processing_time)

                latency = processing_time

             
                time_stamps.append(elapsed_time)
                throughput_data.append(throughput)
           
                packet_loss = ((total_frames_expected - total_frames_received) / total_frames_expected) * 100 if total_frames_expected > 0 else 0
                packet_loss_data.append(packet_loss)

                print(f"[Client] Throughput: {throughput:.2f} bytes/sec, Latency: {latency:.2f} seconds, Packet Loss: {packet_loss:.2f}%")

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')

            except Exception as e:
                logging.error(f"Error receiving video frames: {e}")
                client_disconnected = True  # Set disconnect flag
                break
    finally:
        client_socket.close()
        if client_disconnected:
            print("Client disconnected")

#PERFORMACE
def calculate_average_latency(latency_data):
    if not latency_data:
        return []
    return [np.mean(latency_data[:i+1]) for i in range(len(latency_data))]

def moving_average(data, window_size):
    """Calculate the moving average of a given data list."""
    if len(data) < window_size:
        return data  
    return np.convolve(data, np.ones(window_size) / window_size, mode='valid')


def plot_throughput():
    if not time_stamps or not throughput_data:
        print("Throughput data is empty, cannot plot!")
        return

    smoothed_throughput = moving_average(throughput_data, window_size=5)
 
    plt.figure(figsize=(8, 5))
    plt.plot(time_stamps[len(time_stamps) - len(smoothed_throughput):], smoothed_throughput, label='Smoothed Throughput', color='blue')
    plt.title('Throughput Over Time')
    plt.ylabel('Throughput (bytes/sec)')
    plt.xlabel('Time (seconds)')
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_latency():
    if not time_stamps or not latency_data:
        print("Latency data is empty, cannot plot!")
        return

    smoothed_latency = moving_average(latency_data, window_size=5)

    plt.figure(figsize=(8, 5))
    plt.plot(time_stamps[len(time_stamps) - len(smoothed_latency):], smoothed_latency, label='Smoothed Latency', color='green')
    plt.title('Latency Over Time')
    plt.ylabel('Latency (seconds)')
    plt.xlabel('Time (seconds)')
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_packet_loss():
    if not time_stamps or not packet_loss_data:
        print("Packet loss data is empty, cannot plot!")
        return

   
    smoothed_packet_loss = moving_average(packet_loss_data, window_size=5)

   
    plt.figure(figsize=(8, 5))
    plt.plot(time_stamps[len(time_stamps) - len(smoothed_packet_loss):], smoothed_packet_loss, label='Smoothed Packet Loss', color='red')
    plt.title('Packet Loss Over Time')
    plt.ylabel('Packet Loss (%)')
    plt.xlabel('Time (seconds)')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

def plot_average_latency_vs_packet_loss():
    if not latency_data or not packet_loss_data:
        print("Data is missing for Average Latency vs Packet Loss, cannot plot!")
        return

   
    average_latency = calculate_average_latency(latency_data)  # Calculate average latency in ms
    packet_loss_percentage = np.array(packet_loss_data)

    mask = ~np.isnan(average_latency) & ~np.isnan(packet_loss_percentage)
    average_latency = np.array(average_latency)[mask]
    packet_loss_percentage = packet_loss_percentage[mask]

    plt.figure(figsize=(8, 5))
    plt.plot(average_latency * 1000, packet_loss_percentage, label='Average Latency vs Packet Loss', color='orange', linestyle='-')
    plt.title('Average Latency vs Packet Loss')
    plt.ylabel('Packet Loss (%)')
    plt.xlabel('Average Latency (ms)')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


def plot_sorted_latency_vs_bandwidth():
    if not throughput_data or not latency_data:
        print("Data is missing for Latency vs Bandwidth, cannot plot!")
        return

   
    smoothed_bandwidth = moving_average(throughput_data, window_size=5)
    smoothed_latency = moving_average(latency_data, window_size=5)

    # Ensure both arrays are the same length for plotting
    min_length = min(len(smoothed_bandwidth), len(smoothed_latency))

    # Prepare data for sorting
    data = list(zip(smoothed_bandwidth[:min_length], smoothed_latency[:min_length] * 1000))  # convert latency to ms
    data.sort(key=lambda x: x[0])  # sort by bandwidth

    sorted_bandwidth, sorted_latency = zip(*data)  # unzip into separate lists

    plt.figure(figsize=(8, 5))
    plt.plot(sorted_bandwidth, sorted_latency, label='Sorted Latency vs Bandwidth', color='purple', linestyle='-')
    plt.title('Sorted Latency vs Bandwidth')
    plt.ylabel('Latency (ms)')
    plt.xlabel('Bandwidth (bytes/sec)')
    plt.xscale('log')  
    plt.yscale('linear') 
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

def generate_performance_graph():
    plot_throughput()
    plot_latency()
    plot_packet_loss()
    plot_sorted_latency_vs_bandwidth() 
    plot_average_latency_vs_packet_loss() 
 

def compute_performance_matrix():
    if not throughput_data or not latency_data or not packet_loss_data:
        return {}

    avg_throughput = round(np.mean(throughput_data), 3) if throughput_data else 0
    avg_latency = round(np.mean(latency_data) * 1000, 3)  
    max_latency = round(np.max(latency_data) * 1000, 3)  
    min_latency = round(np.min(latency_data) * 1000, 3) 
    avg_packet_loss = round(np.mean(packet_loss_data), 3) if packet_loss_data else 0

    
    total_frames = total_frames_received
    frame_loss = total_frames_expected - total_frames_received

   
    performance_matrix = {
        "Average Throughput (bytes/sec)": avg_throughput,
        "Average Latency (ms)": avg_latency,
        "Max Latency (ms)": max_latency,
        "Min Latency (ms)": min_latency,
        "Average Packet Loss (%)": avg_packet_loss,
        "Total Frames Expected": total_frames_expected,
        "Total Frames Received": total_frames_received,
        "Frame Loss": frame_loss,
    }

    return performance_matrix


@app.route('/performance_matrix')
def performance_matrix():
    matrix = compute_performance_matrix()
    return jsonify(matrix)


@app.route('/')
def client_ui():
    return render_template('client_login.html') 

@app.route('/search')
def search():
    return render_template('client_search.html')  

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
    global client_name, streamer_name, chat_socket  
    streamer_name = request.form.get('streamer_name')
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
                    has_voted = False 
                    print(f"[Chat Listener] New Poll received: {poll_options}")

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
        print(f"[Client] Sending message: {message}")
        chat_socket.sendall(f"{client_name}: {message}".encode())
        print(f"[Client] Message sent: {message}")
    else:
        print("[Client] No message to send")
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
    
@app.route('/get_poll', methods=['GET'])
def get_poll():
    global poll_options 
    if poll_options:
        return jsonify(poll_options), 200  
    else:
        return jsonify({"message": "No active poll at the moment"}), 200 

@app.route('/vote/<int:option>', methods=['POST'])
def vote(option):
    global chat_socket, has_voted

    if has_voted:
        
        return jsonify({"alert": "Already Given Vote"}), 400

    vote_message = f"-VOTE-{option}"
    chat_socket.sendall(vote_message.encode())
    has_voted = True 
    print(f"[Client] Vote sent: {vote_message}")

    return '', 204 

@app.route('/get_messages', methods=['GET'])
def get_messages():
    return jsonify(messages_list), 200  

def start_client():
    app.run(debug=True, port=5001)

if __name__ == '__main__':
    start_client()
    generate_performance_graph()