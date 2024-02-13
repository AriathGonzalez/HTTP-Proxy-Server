'''
Client Process		Server Proc
						- Welcoming Socket
- Client Socket 
			(<- 3-way Handshake -> )
						- Conn socket
			(bytes ->)
			(<- bytes)

'''
import sys, os, time, select
from socket import *
        
CACHE = "cache/"

def fetchFromCache(fileToUse):
    response = b''
    with open(fileToUse, 'rb') as f:
        response += f.read()
    return response

def saveInCache(fileToUse, message):
    f = open(fileToUse, 'w')    # Create file in cache if it does not exist
    with open(fileToUse, 'wb') as f:
        f.write(message)

def extractHostPath(message):
    """Extracts host and path from HTTP request."""
    firstLine = message.split("\n")[0]
    host = firstLine.split(' ')[1]
    path = ""
    firstSlashIdx = host[1:].find('/')
    if firstSlashIdx != -1:
        path = host[firstSlashIdx + 1:]
        host = host[:firstSlashIdx + 1]
    return (host, path)

def startProxyServer():
    """Starts the proxy server."""
    # The proxy server is listening at 8888 
    tcpSerSock = socket(AF_INET, SOCK_STREAM)
    tcpSerSock.setblocking(0)
    tcpSerSock.bind((sys.argv[1], 8888))
    tcpSerSock.listen(100)
    
    inputs = {tcpSerSock}
    print("Ready to serve...")
    while inputs:
        readable, _, exceptional = select.select(inputs, [], inputs)
        for s in readable:
            if s is tcpSerSock:
                # Client connects to welcoming socket, Proxy intercepts and reads
                # 1) tcp socket reading from client
                tcpCliSock, addr = s.accept()   
                tcpCliSock.setblocking(0)
                print('Received a connection from:', addr)

                # Add new client socket to list of sockets to monitor
                inputs.add(tcpCliSock)
            else:
                try:
                    # Client sends HTTP request, Proxy intercepts and reads
                    # 2) proxy reads from client
                    message = s.recv(1024)

                    if message:
                        print(message)
                        host, path = extractHostPath(message.decode())

                        fileToUse = CACHE + host[1:]

                        # Check whether the file exists in the cache
                        if os.path.exists(fileToUse):
                            fileModifiedTime = os.path.getmtime(fileToUse)
                            currTime = time.time()
                            age = currTime - fileModifiedTime
                            print("File age: ", age)

                            if age > MAX_AGE:
                                os.remove(fileToUse)    # Discard from cache
                            else:
                                # Proxy server finds a cache hit and generates a response message
                                print("Fetching ", host[1: ], " from cache...")
                                response = fetchFromCache(fileToUse)
                                s.sendall(response)
                                continue

                        else:
                            print("Fetching ", host[1: ], " from origin server...")

                            # Proxy sends request on behalf of client to web server
                            # 3) proxy sends to webserver
                            request = f"GET /{path} HTTP/1.1\r\nHost:{host[1:]}\r\nConnection: close\r\n\r\n"
                            destSocket = socket(AF_INET, SOCK_STREAM)
                            destSocket.connect((host[1:], 80))
                            destSocket.sendall(request.encode())

                            # Webserver sends response to client, Proxy intercepts and reads
                            # 4) proxy reads from webserver
                            response = b''
                            while True:
                                # (4) Webserver sends the response back to the Proxy Server
                                chunk = destSocket.recv(4096)

                                # No more data to send
                                if not chunk:
                                    break
                                response += chunk
                            
                            saveInCache(fileToUse, response)
                            destSocket.close()
                            # Proxy sends response to client on behalf of webserver
                            # 5) proxy sends to client
                            s.sendall(response)
                    else:
                        inputs.remove(s)
                        s.close()
                except OSError as e:
                    print(f"Error {e} with socket: {s}")
                    inputs.remove(s)
                    s.close()  
        for s in exceptional:
            inputs.remove(s)
            s.close()

    tcpSerSock.close()
if __name__ == "__main__":
    if len(sys.argv) <= 2:
        print('Usage : "python ProxyServer.py server_ip max_age"\n[server_ip : It is the IP Address Of Proxy Server]\n[max_age: It is the max age (in seconds) for an item in the cache.]')
        sys.exit(2)

    if int(sys.argv[2]) < 0:
        print("Error: max_age must at least be 0")
        sys.exit(2)

    if not os.path.exists(CACHE):
        os.makedirs(CACHE)

    MAX_AGE = int(sys.argv[2])

    startProxyServer()
