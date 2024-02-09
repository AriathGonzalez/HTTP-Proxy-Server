'''
Client Process		Server Proc
						- Welcoming Socket
- Client Socket 
			(<- 3-way Handshake -> )
						- Conn socket
			(bytes ->)
			(<- bytes)

'''
import sys, os, time, select, queue
from socket import *

# Define cache directory
CACHE = "cache/"

def fetchFromCache(fileToUse):
    """Fetches data from cache file."""
    response = b''
    with open(fileToUse, 'rb') as f:
        response += f.read()
    return response

def saveInCache(fileToUse, message):
    """Saves data to cache file."""
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
    outputs = set()
    messageQueues = {}

    print('Ready to serve...')
    while inputs:
        readable, writable, exceptional = select.select(inputs, outputs, inputs)
        for s in readable:
            if s is tcpSerSock:
                # 1) The client sends an HTTP request to retrieve an object
                tcpCliSock, addr = s.accept()   
                tcpCliSock.setblocking(0)
                print('Received a connection from:', addr)

                # Add new client socket to list of sockets to monitor
                inputs.add(tcpCliSock)
                messageQueues[tcpCliSock] = queue.Queue()
            else:
                if s not in messageQueues:
                    messageQueues[s] = queue.Queue()

				# (2) This request gets received by the proxy and it creates a 
                # fresh HTTP request for the same object to the origin server
                message = s.recv(1024).decode()

                if message:
                    print(message)
                    messageQueues[s].put(message)
                    if s not in outputs:
                        outputs.add(s)
                else:
                    if s in outputs:
                        outputs.remove(s)
                    inputs.remove(s)
                    s.close()
                    del messageQueues[s]
                    
        for s in writable:
            try:
                nextMsg = messageQueues[s].get_nowait()
            except queue.Empty:
                outputs.remove(s)
            else:
                host, path = extractHostPath(nextMsg)
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
                        print("Fetching ", fileToUse, " from cache...")
                        response = fetchFromCache(fileToUse)
                        s.sendall(response)
                        continue
                    
                print("Fetching ", fileToUse, " from origin server...")

				# (3) Send the new HTTP request to the Web Server
                destSocket = socket(AF_INET, SOCK_STREAM)
                destSocket.connect((host[1:], 80))

                request = f"GET /{path} HTTP/1.1\r\nHost:{host[1:]}\r\nConnection: close\r\n\r\n"
                destSocket.sendall(request.encode())

                response = b''
                while True:
                    # (4) Webserver sends the response back to the Proxy Server
                    chunk = destSocket.recv(4096)

                    # No more data to send
                    if len(chunk) == 0:
                        break
                    response += chunk
                
                # Must modify page to prevent favicon requests.
                response = response.replace(b'</title>', b'</title>\n<link rel="icon" href="data:," />')

                saveInCache(fileToUse, response)
                destSocket.close()

				# (5) The proxy server creates a new HTTP response along with the object 
				# and sends back to the client
                s.sendall(response)
                
        for s in exceptional:
            inputs.remove(s)
            if s in outputs:
                outputs.remove(s)
            s.close()
            del messageQueues[s]

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
