import socket
import threading

# Define the server address and port
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 12345

# Create a TCP/IP socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind the socket to the address and port
server_socket.bind((SERVER_HOST, SERVER_PORT))

# Listen for incoming connections
server_socket.listen(5)
print(f"Server started at {SERVER_HOST}:{SERVER_PORT}")

# Function to handle client connections
def handle_client(client_socket):
    while True:
        try:
            # Receive data from the client
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                break
            print(f"Received from client: {data}")

            # Send a response back to the client
            response = f"Echo: {data}"
            client_socket.send(response.encode('utf-8'))
        except ConnectionResetError:
            break

    # Close the client socket
    client_socket.close()

# Main server loop
while True:
    # Accept a new client connection
    client_socket, client_address = server_socket.accept()
    print(f"New connection from {client_address}")

    # Create a new thread to handle the client
    client_thread = threading.Thread(target=handle_client, args=(client_socket,))
    client_thread.start()