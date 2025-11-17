import sys, socket

from ServerWorker import ServerWorker

class Server:	
	
	def main(self):
		try:
			SERVER_PORT = int(sys.argv[1])
		except:
			print("[Usage: Server.py Server_port]\n")
			return
		
		rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		rtspSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

		rtspSocket.settimeout(1.0)

		try:
			rtspSocket.bind(('', SERVER_PORT))
			rtspSocket.listen(5)        
		except OSError as e:
			print(f"Error {e}")
			print(f"Port {SERVER_PORT} might be in use. Try lsof -ti :{SERVER_PORT} | xargs kill -9")
			return
		# Receive client info (address,port) through RTSP/TCP session
		try:
			while True:
				try:
					clientInfo = {}
					clientInfo['rtspSocket'] = rtspSocket.accept()
					print(f"Client connected from {clientInfo['rtspSocket'][1]}")
					ServerWorker(clientInfo).run()		
				except socket.timeout:
					continue
				except Exception as e:
					print(f"Client error: {e}")
					continue
		except KeyboardInterrupt:
			print("\n\n Server shutting down...")
		finally:
			rtspSocket.close()
			print("Server stopped")
		

if __name__ == "__main__":
	(Server()).main()