from tkinter import *
import tkinter.messagebox
import socket
import threading
import os
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
from queue import Queue
import time

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

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

        # --- Buffering configuration ---
        self.frameBuffer = Queue(maxsize=50)  # max frames to cache
        self.MIN_BUFFER = 20                  # start playback when buffer reaches this
        # start renderer thread (daemon) so it runs in background
        self.startBufferRenderer()

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
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def exitClient(self):
        """Teardown button handler."""
        self.sendRtspRequest(self.TEARDOWN)		
        self.master.destroy() # Close the gui window

         # Delete the cache image from video
        try:
            os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)
        except OSError:
            pass

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)

    def playMovie(self):
        """Play button handler."""
        if self.state == self.READY:
            # Create a new thread to listen for RTP packets
            threading.Thread(target=self.listenRtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.sendRtspRequest(self.PLAY)

    def listenRtp(self):        
        """Listen for RTP packets."""
        
        # Buffer for reassembly of fragmented frames
        frameBuffer = b""
        
        while True:
            try:
                data = self.rtpSocket.recv(20480) # Receive packet
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)
                    
                    payload = rtpPacket.getPayload()
                    marker = rtpPacket.marker()
                    
                    # Reassemble fragments into a full frame
                    frameBuffer += payload
                    
                    if marker == 1:
                        # Full frame received in frameBuffer (bytes)
                        # Instead of rendering immediately, push into frameBuffer queue
                        try:
                            if not self.frameBuffer.full():
                                # put a copy of the bytes into the queue
                                self.frameBuffer.put(frameBuffer)
                            else:
                                # If buffer full, drop oldest frame then put new one (to keep fresh)
                                try:
                                    self.frameBuffer.get_nowait()
                                    self.frameBuffer.put(frameBuffer)
                                except:
                                    pass
                        except:
                            pass

                        # update last received frame number (for bookkeeping)
                        currFrameNbr = rtpPacket.seqNum()
                        self.frameNbr = currFrameNbr

                        # reset reassembly buffer
                        frameBuffer = b""

            except:
                # Stop listening upon requesting PAUSE or TEARDOWN
                if hasattr(self, 'playEvent') and self.playEvent.isSet(): 
                    break
                
                if self.teardownAcked == 1:
                    try:
                        self.rtpSocket.shutdown(socket.SHUT_RDWR)
                        self.rtpSocket.close()
                    except:
                        pass
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
        try:
            photo = ImageTk.PhotoImage(Image.open(imageFile))
            self.label.configure(image = photo, height = 500) 
            self.label.image = photo
        except Exception as e:
            # If there's an error loading image, ignore to keep renderer running
            print("updateMovie error:", e)

    def connectToServer(self):
        """Connect to the Server. Start a new RTSP/TCP session."""
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except:
            tkinter.messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)

    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""	
        #-------------
        # TO COMPLETE
        #-------------
        
        # Setup request
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply).start()
            # Update RTSP sequence number.
            self.rtspSeq += 1
            
            # Write the RTSP request to be sent.
            request = f"SETUP {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nTransport: RTP/UDP; client_port= {self.rtpPort}\n"
            
            # Keep track of the sent request.
            self.requestSent = self.SETUP
        
        # Play request
        elif requestCode == self.PLAY and self.state == self.READY:
            # Update RTSP sequence number.
            self.rtspSeq += 1
            
            # Write the RTSP request to be sent.
            request = f"PLAY {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}\n"
            
            # Keep track of the sent request.
            self.requestSent = self.PLAY 
        
        # Pause request
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            # Update RTSP sequence number.
            self.rtspSeq += 1
            
            # Write the RTSP request to be sent.
            request = f"PAUSE {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}\n"
            
            # Keep track of the sent request.
            self.requestSent = self.PAUSE
            
        # Teardown request
        elif requestCode == self.TEARDOWN and not self.state == self.INIT:
            # Update RTSP sequence number.
            self.rtspSeq += 1
            
            # Write the RTSP request to be sent.
            request = f"TEARDOWN {self.fileName} RTSP/1.0\nCSeq: {self.rtspSeq}\nSession: {self.sessionId}\n"
            
            # Keep track of the sent request.
            self.requestSent = self.TEARDOWN
        else:
            return
        
        # Send the RTSP request using rtspSocket.
        try:
            self.rtspSocket.send(request.encode())
        except:
            print("Failed to send RTSP request.")
        
        print('\nData sent:\n' + request)
    
    def recvRtspReply(self):
        """Receive RTSP reply from the server."""
        while True:
            try:
                reply = self.rtspSocket.recv(1024)
            except:
                reply = None
            
            if reply: 
                try:
                    self.parseRtspReply(reply.decode("utf-8"))
                except Exception as e:
                    print("parseRtspReply error:", e)
            
            # Close the RTSP socket upon requesting Teardown
            if self.requestSent == self.TEARDOWN:
                try:
                    self.rtspSocket.shutdown(socket.SHUT_RDWR)
                    self.rtspSocket.close()
                except:
                    pass
                break
    
    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = data.split('\n')
        # basic defensive parsing
        try:
            seqNum = int(lines[1].split(' ')[1])
        except:
            return
        
        # Process only if the server reply's sequence number is the same as the request's
        if seqNum == self.rtspSeq:
            try:
                session = int(lines[2].split(' ')[1])
            except:
                session = 0
            # New RTSP session ID
            if self.sessionId == 0 and session != 0:
                self.sessionId = session
            
            # Process only if the session ID is the same (or if not set)
            if self.sessionId == session or self.sessionId == 0:
                # success code 200
                try:
                    code = int(lines[0].split(' ')[1])
                except:
                    code = 0
                if code == 200: 
                    if self.requestSent == self.SETUP:
                        # Update RTSP state.
                        self.state = self.READY
                        
                        # Open RTP port.
                        self.openRtpPort()
                        # Ensure buffer empty at start
                        self.clearBuffer()
                        # Start buffering (renderer thread already started in __init__)
                    elif self.requestSent == self.PLAY:
                        self.state = self.PLAYING
                    elif self.requestSent == self.PAUSE:
                        self.state = self.READY
                        
                        # The play thread exits. A new thread is created on resume.
                        if hasattr(self, 'playEvent'):
                            self.playEvent.set()
                        # On pause, clear buffer to avoid playing stale frames when resume
                        self.clearBuffer()
                    elif self.requestSent == self.TEARDOWN:
                        self.state = self.INIT
                        
                        # Flag the teardownAcked to close the socket.
                        self.teardownAcked = 1 
                        # Clear buffer
                        self.clearBuffer()
    
    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""
        #-------------
        # TO COMPLETE
        #-------------
        # Create a new datagram socket to receive RTP packets from the server
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Set the timeout value of the socket to 0.5sec
        self.rtpSocket.settimeout(0.5)
        
        try:
            # Bind the socket to the address using the RTP port given by the client user
            self.rtpSocket.bind(('', self.rtpPort))
        except:
            tkinter.messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else: # When the user presses cancel, resume playing.
            self.playMovie()

    # ------------------ Buffer renderer methods ------------------
    def startBufferRenderer(self):
        """Start background thread that renders frames from buffer to GUI."""
        t = threading.Thread(target=self.renderVideo, daemon=True)
        t.start()

    def renderVideo(self):
        """
        Continuously check the frameBuffer and render frames when:
        - client state is PLAYING
        - buffer has at least MIN_BUFFER frames (prebuffering)
        """
        # Sleep a bit initially to let setup happen
        time.sleep(0.1)
        while True:
            # If playing, only start rendering when buffer has enough frames
            if self.state == self.PLAYING:
                # Wait until minimum buffer is available
                if self.frameBuffer.qsize() < self.MIN_BUFFER:
                    # small sleep to avoid busy waiting
                    time.sleep(0.01)
                    continue

                # Pop a frame and render it
                try:
                    frameBytes = self.frameBuffer.get(timeout=1.0)
                    # write frame to cache file and update GUI
                    imageFile = self.writeFrame(frameBytes)
                    self.updateMovie(imageFile)
                    # Sleep to match expected frame rate (server sends every 50ms)
                    time.sleep(0.05)
                except Exception as e:
                    # If no frame available or error, wait a bit then continue
                    # print("renderVideo exception:", e)
                    time.sleep(0.01)
                    continue
            else:
                # Not playing: sleep to reduce CPU usage
                time.sleep(0.05)

    def clearBuffer(self):
        """Empty the frame buffer queue."""
        try:
            while not self.frameBuffer.empty():
                try:
                    self.frameBuffer.get_nowait()
                except:
                    break
        except:
            pass
