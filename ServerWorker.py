from random import randint
import sys, traceback, threading, socket

from VideoStream import VideoStream
from RtpPacket import RtpPacket
from time import time

class ServerWorker:
	SETUP = 'SETUP'
	PLAY = 'PLAY'
	PAUSE = 'PAUSE'
	TEARDOWN = 'TEARDOWN'
	MAX_PAYLOAD_SIZE = 1400
	
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	OK_200 = 0
	FILE_NOT_FOUND_404 = 1
	CON_ERR_500 = 2
	
	clientInfo = {}
	
	def __init__(self, clientInfo):
		self.clientInfo = clientInfo
		
	def run(self):
		threading.Thread(target=self.recvRtspRequest).start()
	
	def recvRtspRequest(self):
		"""Receive RTSP request from the client."""
		connSocket = self.clientInfo['rtspSocket'][0]
		while True:            
			data = connSocket.recv(256)
			if data:
				print("Data received:\n" + data.decode("utf-8"))
				self.processRtspRequest(data.decode("utf-8"))
	
	def processRtspRequest(self, data):
		"""Process RTSP request sent from the client."""
		# Get the request type
		request = data.split('\n')
		line1 = request[0].split(' ')
		requestType = line1[0]
		
		# Get the media file name
		filename = line1[1]
		
		# Get the RTSP sequence number 
		seq = request[1].split(' ')
		
		# Process SETUP request
		if requestType == self.SETUP:
			if self.state == self.INIT:
				# Update state
				print("processing SETUP\n")
				
				try:
					self.clientInfo['videoStream'] = VideoStream(filename)
					self.state = self.READY
				except IOError:
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
				
				# Generate a randomized RTSP session ID
				self.clientInfo['session'] = randint(100000, 999999)
				
				# Send RTSP reply
				self.replyRtsp(self.OK_200, seq[1])
				
				# Get the RTP/UDP port from the last line
				self.clientInfo['rtpPort'] = request[2].split(' ')[3]
		
		# Process PLAY request 		
		elif requestType == self.PLAY:
			if self.state == self.READY:
				print("processing PLAY\n")
				self.state = self.PLAYING
				
				# Create a new socket for RTP/UDP
				self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				
				self.replyRtsp(self.OK_200, seq[1])
				
				# Create a new thread and start sending RTP packets
				self.clientInfo['event'] = threading.Event()
				self.clientInfo['worker']= threading.Thread(target=self.sendRtp) 
				self.clientInfo['worker'].start()
				self.clientInfo['rtpSeqNum'] = 0
		
		# Process PAUSE request
		elif requestType == self.PAUSE:
			if self.state == self.PLAYING:
				print("processing PAUSE\n")
				self.state = self.READY
				
				self.clientInfo['event'].set()
			
				self.replyRtsp(self.OK_200, seq[1])
		
		# Process TEARDOWN request
		elif requestType == self.TEARDOWN:
			print("processing TEARDOWN\n")

			self.clientInfo['event'].set()
			
			self.replyRtsp(self.OK_200, seq[1])
			
			# Close the RTP socket
			self.clientInfo['rtpSocket'].close()

		
	def replyRtsp(self, code, seq):
		"""Send RTSP reply to the client."""
		if code == self.OK_200:

			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())
		
		# Error messages
		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")

	def sendRtp(self):
			"""Send RTP packets over UDP."""
			rtpSocket = self.clientInfo['rtpSocket']

			address = self.clientInfo['rtspSocket'][1][0]
			rtpPort = int(self.clientInfo['rtpPort'])
			
			while True:
				self.clientInfo['event'].wait(0.05) 
				
				if self.clientInfo['event'].isSet(): 
					break 
				data = self.clientInfo['videoStream'].nextFrame()
				if data: 
					# FRAGMENTATION
					frameNumber = self.clientInfo['videoStream'].frameNbr()
					
					# get timestamp
					current_timestamp = int(time())
					
					payload = data
					size = len(payload)
					offset = 0
					
					# Cut frame
					while offset < size:
						chunk = payload[offset : offset + self.MAX_PAYLOAD_SIZE]
						offset += len(chunk)
						
						if offset >= size:
							marker = 1
						else:
							marker = 0

						seqnum = self.clientInfo['rtpSeqNum']
						self.clientInfo['rtpSeqNum'] += 1
						
						try:
							# send packet
							packet = self.makeRtp(chunk, seqnum, current_timestamp, marker)
							rtpSocket.sendto(packet, (address, rtpPort))
						except:
							print("Connection Error")


	def makeRtp(self, payload, seqnum, timestamp, marker):
		"""RTP-packetize the video data."""
		version = 2
		padding = 0
		extension = 0
		cc = 0
		pt = 26 
		ssrc = 1111 
		rtpPacket = RtpPacket()
		# Encode the packet with the provided header fields and payload
		rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, timestamp, payload)
		# Return the packet as a byte stream to be sent over UDP
		return rtpPacket.getPacket()