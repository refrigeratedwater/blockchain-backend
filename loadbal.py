import socket

#List of servers
servers = [('localhost', 5001), ('localhost', 5002)]
server_index = 0 

# Create socket object
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind socket to a port
sock.bind(('localhost', 5000))

#Listen for connections
sock.listen(5)

while True:
    client_sock, client_addr = sock.accept()
    print('Recieved connection from: ', client_addr)
    
    # Choose server to forward connection (round robin)
    server_addr = servers[server_index]
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.connect(server_addr)
    server_index = (server_index + 1) % len(servers) # Update index for next connection
    
    #Forward the connection
    data = client_sock.recv(1024)
    while data:
        server_sock.sendall(data)
        data = client_sock.recv(1024)
    
    client_sock.close()
    server_sock.close()    