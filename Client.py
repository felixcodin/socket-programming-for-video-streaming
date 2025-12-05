from tkinter import *
import tkinter.messagebox as tkMessageBox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
import time 

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"
CACHE_SIZE = 10 # Kích thước buffer cho caching (Có thể điều chỉnh)

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		
		# Khởi tạo biến Caching/Pre-buffering
		self.isCaching = False
		self.frameCache = []
		
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		self.label.configure(text="Press Setup.", bg="white")
		
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)
		
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)
		
		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 
	
	def setupMovie(self):
		"""Setup button handler. Bắt đầu quá trình caching."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
			# Sau khi nhận 200 OK cho SETUP, parseRtspReply sẽ gửi PLAY để bắt đầu caching

	# BỔ SUNG: Fix lỗi FileNotFoundError và đảm bảo Teardown dừng thread
	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		self.master.destroy() 
		
		# Xóa file cache tạm (ảnh frame cuối cùng)
		try:
			os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) 
		except FileNotFoundError:
			pass 
		except Exception as e:
			print(f"Error during file cleanup: {e}")

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING or self.isCaching:
			# Dừng luồng play cache/live streaming
			if hasattr(self, 'playEvent'):
				self.playEvent.set()
			self.sendRtspRequest(self.PAUSE)
	
	def playMovie(self):
		"""Play button handler (Đã sửa cho Caching/Live Streaming)."""
		if self.state == self.READY:
			
			# Nếu vẫn đang đệm, thông báo chờ
			if self.isCaching and len(self.frameCache) < CACHE_SIZE:
				tkMessageBox.showinfo("Client Status", f"Buffer is still loading! Please wait.")
				return
				
			# Nếu cache đã đầy, bắt đầu phát từ cache
			if len(self.frameCache) >= CACHE_SIZE or (not self.isCaching and len(self.frameCache) > 0):
				self.state = self.PLAYING
				self.label.configure(text=f"Streaming from cache...", bg="blue")
				self.playEvent = threading.Event()
				self.playEvent.clear()
				threading.Thread(target=self.playFromCache).start()
			else:
				# Nếu không có cache, gửi PLAY để Server gửi live stream
				self.sendRtspRequest(self.PLAY)
				self.state = self.PLAYING 
				self.playEvent = threading.Event()
				self.playEvent.clear()
				
				# Khởi động lại luồng nhận RTP nếu nó đã bị dừng
				if not hasattr(self, 'rtpThread') or not self.rtpThread.is_alive():
					self.rtpThread = threading.Thread(target=self.recvRtpPacket)
					self.rtpThread.start()
	
	def playFromCache(self):
		"""Phát các frame đã đệm từ bộ nhớ (Cache)."""
		
		PLAYBACK_INTERVAL = 0.05 # Tốc độ phát 20 FPS (1/20)
		
		while self.frameCache and self.state == self.PLAYING and not self.playEvent.isSet():
			try:
				framePayload = self.frameCache.pop(0) 
				self.frameNbr += 1
				self.updateMovie(self.writeFrame(framePayload)) 
				
				time.sleep(PLAYBACK_INTERVAL) 
				
			except IndexError:
				break
			except Exception as e:
				print(f"Error playing from cache: {e}")
				break
				
		# Nếu cache trống trong khi vẫn đang PLAYING và không phải PAUSE/TEARDOWN
		if self.state == self.PLAYING and not self.playEvent.isSet():
			self.label.configure(text="Streaming live (Cache empty)...", bg="green")


	def recvRtpPacket(self):		
		"""Listen for RTP packets (Đã thêm logic Caching)."""
		while True:
			try:
				# Tăng buffer size cho HD video
				data = self.rtpSocket.recv(20480) 
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					
					currFrameNbr = rtpPacket.seqNum()
					
					# Logic Caching: Fill cache
					if self.isCaching:
						self.frameCache.append(rtpPacket.getPayload())
						
						self.label.configure(text=f"Buffering: {len(self.frameCache)}/{CACHE_SIZE} frames...", bg="yellow")
						
						if len(self.frameCache) >= CACHE_SIZE:
							self.isCaching = False
							# KHÔNG CẦN GỬI PAUSE/SETUP, CHỈ THAY ĐỔI TRẠNG THÁI NỘI BỘ
							self.label.configure(text="Buffer ready! Press PLAY.", bg="green")
							
					# Logic Live Streaming: Phát ngay nếu cache hết
					elif self.state == self.PLAYING and not self.frameCache:
						
						if currFrameNbr > self.frameNbr: # Discard the late packet
							self.frameNbr = currFrameNbr
							self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
							
			except:
				# Stop listening upon receiving ACK for TEARDOWN request
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break
				# Nếu luồng đang bị dừng (do Pause)
				if hasattr(self, 'playEvent') and self.playEvent.isSet():
					break
					
	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()
		
		return cachename
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = photo, height=288) 
		self.label.image = photo
		
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		
		self.rtspSeq += 1
		request = ""

		# Setup request
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			
			request += "SETUP " + str(self.fileName) + " RTSP/1.0\r\n"
			request += "CSeq: " + str(self.rtspSeq) + "\r\n"
			request += "Transport: RTP/UDP; client_port= " + str(self.rtpPort) + "\r\n\r\n"
			
			self.requestSent = self.SETUP
		
		# Play request
		elif requestCode == self.PLAY and self.state == self.READY:
				request += "PLAY " + str(self.fileName) + " RTSP/1.0\r\n"
				request += "CSeq: " + str(self.rtspSeq) + "\r\n"
				request += "Session: " + str(self.sessionId) + "\r\n\r\n"
				self.requestSent = self.PLAY

		
		# Pause request
		elif requestCode == self.PAUSE and (self.state == self.PLAYING or self.isCaching):
			self.state = self.READY # Chuyển về READY
			request += "PAUSE " + str(self.fileName) + " RTSP/1.0\r\n"
			request += "CSeq: " + str(self.rtspSeq) + "\r\n"
			request += "Session: " + str(self.sessionId) + "\r\n\r\n"
			self.requestSent = self.PAUSE
			
		# Teardown request
		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
			if hasattr(self, 'playEvent'):
				self.playEvent.set() # Dừng luồng phát/nhận
			
			request += 'TEARDOWN ' + self.fileName + ' RTSP/1.0\r\n'
			request += 'CSeq: ' + str(self.rtspSeq) + '\r\n'
			request += 'Session: ' + str(self.sessionId) + '\r\n\r\n'
			
			self.requestSent = self.TEARDOWN
		else:
			return
		
		self.rtspSocket.sendall(request.encode("utf-8"))
		
		print('\nData sent:\n' + request)
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			try:
				reply = self.rtspSocket.recv(1024)
			except:
				break # Socket closed
			
			if reply: 
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket upon receiving ACK for Teardown
			if self.teardownAcked == 1:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		statusLine = lines[0].strip() 
		
		if int(statusLine.split(' ')[1]) != 200:
			print(f"RTSP Error: {statusLine}")
			print('\nData received:\n' + data)
			return

		# Lấy CSeq
		cseqLine = lines[1].strip()
		try:
			seqNum = int(cseqLine.split(' ')[1])
		except:
			print("Error parsing CSeq line.")
			print('\nData received:\n' + data)
			return

		# Process only if the server reply's sequence number is the same as the request's
		if seqNum == self.rtspSeq:
			# Lấy Session ID
			sessionLine = lines[2].strip()
			try:
				session = int(sessionLine.split(' ')[1])
			except:
				session = 0 
			
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session
			
			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(statusLine.split(' ')[1]) == 200: 
					if self.requestSent == self.SETUP:
						
						# 1. Update RTSP state.
						self.state = self.READY
						
						# 2. Open RTP port.
						self.openRtpPort() 
						
						# 3. BẮT ĐẦU CACHING: Khởi tạo đệm, chạy luồng nhận, gửi PLAY
						self.isCaching = True
						self.frameCache = []
						self.label.configure(text=f"Buffering: 0/{CACHE_SIZE} frames...", bg="yellow")
						
						self.rtpThread = threading.Thread(target=self.recvRtpPacket)
						self.rtpThread.start()
						
						self.sendRtspRequest(self.PLAY) # Gửi PLAY để server bắt đầu stream
						
					elif self.requestSent == self.PLAY:
						# Server đã xác nhận PLAY. Giữ READY cho đến khi cache đầy/người dùng ấn PLAY
						# Hoặc nếu phát live, không cần làm gì ở đây
						pass 
						
					elif self.requestSent == self.PAUSE:
						self.state = self.READY
						# Luồng play cache đã được dừng trong sendRtspRequest
						
					elif self.requestSent == self.TEARDOWN:
						self.state = self.INIT
						
						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1 
				
		print('\nData received:\n' + data)

	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		
		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)	
		
		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket.settimeout(0.5)
		
		
		try:
			# Bind the socket to the address using the RTP port given by the client user
			self.rtpSocket.bind(('', self.rtpPort))
			print("Binded RTP port: " + str(self.rtpPort))
		except:
			tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: 
			self.playMovie()