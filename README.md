Streaming and Chat Client

Overview:
This project implements a streaming and chat client using Flask and socket programming. The client allows users to join a live stream, participate in a chat,
and engage in live polls. The system also collects network performance metrics such as throughput, latency, and packet loss.

Features:
* User authentication via a dedicated authentication server.
* Real-time video streaming from a streamer to multiple clients.
* Live chat functionality with participants.
* Polling system for interactive audience engagement.
* Performance monitoring (throughput, latency, packet loss).
* Visualization of network performance metrics.

Technologies Used:
-> Python (Flask, OpenCV, NumPy, Matplotlib)
-> Socket Programming (TCP/UDP)
-> HTML, JavaScript (for client-side interaction)
-> MongoDB (for authentication and user management)

Requirements:
* Python 3.x
* Flask
* OpenCV
* NumPy
* Matplotlib
* MongoDB (for user authentication)

Usage:
Running the Client
Start the Flask application:
python client.py
Open a web browser and navigate to http://localhost:5000.
Login using valid credentials.
Join a stream by entering the streamer's name.
The video feed and chat functionalities will be available.

Chat Functionality:
* Messages are sent using the /send_message endpoint.
* Participants list is fetched using /get_participants.
* Poll results are retrieved using /get_poll_results.

Performance Monitoring:
* Performance metrics are computed and displayed via the /performance_matrix endpoint.
* Graphs for network performance are generated using generate_performance_graph().

Video Streaming:
* GET /video_feed - Fetches video frames from the streamer.
* POST /join_stream - Connects the client to the selected stream.

Notes:
-> Ensure the server is running and accessible at the configured IP address.
-> If connection errors occur, verify the network settings and ports (8001, 8002, 8003).
-> Performance graphs require Matplotlib for visualization.

