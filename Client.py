from tkinter import *
import tkinter.messagebox
import socket
import threading
import os
from PIL import Image, ImageTk
import sys, traceback, time
from collections import deque

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

    # Buffer settings (tweak as needed)
    FRAME_RATE = 20                   # expected fps (used for timing)
    BUFFER_MAX_FRAMES = 400           # max frames to keep in memory (e.g. 20s if 20fps -> 20s)
    PREFETCH_FRAMES = 40              # buffer fill threshold before starting playback (~2s)
    SOCKET_TIMEOUT = 0.5              # UDP socket timeout

    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename

        # RTSP control/state
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0

        # Buffer / playback
        self.buffer = deque(maxlen=self.BUFFER_MAX_FRAMES)  # stores frames (bytes)
        self.buffer_lock = threading.Lock()
        self.buffer_start_frame_no = 0    # absolute frame number of buffer[0]
        self.total_frames_received = 0    # absolute frame count received so far
        self.play_index = 0               # absolute frame index we are currently showing
        self.video_ready_event = threading.Event()  # set when buffer has PREFETCH_FRAMES
        self.play_event = threading.Event()        # controls play/pause (set=playing)
        self.stop_receive = threading.Event()      # signal to stop receiver thread

        # Threads
        self.rtp_thread = None
        self.renderer_thread = threading.Thread(target=self.renderVideo, daemon=True)
        self.renderer_thread.start()

        # connect to server
        self.connectToServer()

    # ---------------- GUI ----------------
    def createWidgets(self):
        self.setup = Button(self.master, width=20, text="Setup", command=self.setupMovie)
        self.setup.grid(row=1, column=0, padx=2, pady=2)

        self.start = Button(self.master, width=20, text="Play", command=self.playMovie)
        self.start.grid(row=1, column=1, padx=2, pady=2)

        self.pause = Button(self.master, width=20, text="Pause", command=self.pauseMovie)
        self.pause.grid(row=1, column=2, padx=2, pady=2)

        self.teardown = Button(self.master, width=20, text="Teardown", command=self.exitClient)
        self.teardown.grid(row=1, column=3, padx=2, pady=2)

        # SEEK BACK
        self.backward = Button(self.master, width=20, text="<< Back", command=self.seekBackward)
        self.backward.grid(row=2, column=0, padx=2, pady=2)

        # SEEK FORWARD
        self.forward = Button(self.master, width=20, text="Forward >>", command=self.seekForward)
        self.forward.grid(row=2, column=1, padx=2, pady=2)

        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

        # status label
        self.status_var = StringVar(value="State: INIT")
        self.status = Label(self.master, textvariable=self.status_var)
        self.status.grid(row=3, column=0, columnspan=4, sticky=W+E, padx=5, pady=2)

    # ---------------- RTSP button handlers ----------------
    def setupMovie(self):
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def exitClient(self):
        # send TEARDOWN and cleanup
        if self.state != self.INIT:
            self.sendRtspRequest(self.TEARDOWN)
            # Wait briefly for teardown handshake
            time.sleep(0.2)

        # set teardown flag and stop threads
        self.stop_receive.set()
        self.play_event.clear()
        self.video_ready_event.clear()

        # close sockets if open
        try:
            if hasattr(self, "rtpSocket"):
                self.rtpSocket.close()
        except:
            pass
        try:
            if hasattr(self, "rtspSocket"):
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
        except:
            pass

        # clear buffer and delete cache file
        with self.buffer_lock:
            self.buffer.clear()

        try:
            os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)
        except:
            pass

        self.master.destroy()

    def pauseMovie(self):
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)
            # pause rendering
            self.play_event.clear()
            self.status_var.set("State: PAUSE")

    def playMovie(self):
        # only allow play when READY or currently PAUSED
        if self.state in (self.READY, self.PLAYING):
            # if first play -> start RTP receiver
            if not self.rtp_thread or not self.rtp_thread.is_alive():
                self.stop_receive.clear()
                self.rtp_thread = threading.Thread(target=self.listenRtp, daemon=True)
                self.rtp_thread.start()

            # if buffer hasn't reached prefetch threshold, wait (non-blocking)
            if not self.video_ready_event.is_set():
                self.status_var.set("Buffering...")
            # set play event (renderer will only start when video_ready_event is set)
            self.play_event.set()
            self.sendRtspRequest(self.PLAY)
            self.status_var.set("State: PLAYING")

    # ---------------- SEEK ----------------
    def seekForward(self, sec=2):
        """seek forward by sec seconds (within buffer)."""
        with self.buffer_lock:
            jump = int(sec * self.FRAME_RATE)
            target = self.play_index + jump
            buffer_start = self.buffer_start_frame_no
            buffer_end = buffer_start + len(self.buffer) - 1
            if target > buffer_end:
                # cannot seek past buffer end
                self.play_index = buffer_end
            else:
                self.play_index = target
        self.status_var.set(f"Seek -> frame {self.play_index}")

    def seekBackward(self, sec=2):
        """seek backward by sec seconds (within buffer)."""
        with self.buffer_lock:
            jump = int(sec * self.FRAME_RATE)
            target = self.play_index - jump
            if target < self.buffer_start_frame_no:
                self.play_index = self.buffer_start_frame_no
            else:
                self.play_index = target
        self.status_var.set(f"Seek -> frame {self.play_index}")

    # ---------------- RTP listener (streaming, limited buffer) ----------------
    def listenRtp(self):
        """Receive RTP packets and maintain a limited in-memory buffer (deque)."""
        frameBuffer = b""
        expected_seq = None

        # prepare UDP socket
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtpSocket.settimeout(self.SOCKET_TIMEOUT)
        try:
            self.rtpSocket.bind(('', self.rtpPort))
        except Exception as e:
            tkinter.messagebox.showwarning("Unable to Bind", f"Unable to bind PORT={self.rtpPort}: {e}")
            return

        while not self.stop_receive.is_set():
            try:
                data, _ = self.rtpSocket.recvfrom(65536)
                if not data:
                    continue

                rtpPacket = RtpPacket()
                try:
                    rtpPacket.decode(data)
                except Exception:
                    # if RtpPacket can't decode, skip packet
                    continue

                payload = rtpPacket.getPayload()
                marker = 0
                try:
                    marker = rtpPacket.marker()
                except Exception:
                    # if no marker method, try reading last byte heuristic (fallback)
                    marker = 0

                seq = None
                # try to get seq number from packet if available
                if hasattr(rtpPacket, "seqNum"):
                    try:
                        seq = rtpPacket.seqNum()
                    except Exception:
                        seq = None
                else:
                    # try attribute names used in some RtpPacket implementations
                    seq = getattr(rtpPacket, "seq", None)

                # Very simple sequence handling: if we detect a drop (non-consecutive seq),
                # discard current frameBuffer to avoid heavy corruption.
                if expected_seq is not None and seq is not None:
                    if seq != expected_seq:
                        # packet loss detected -> reset frameBuffer (drop partial)
                        frameBuffer = b""
                expected_seq = (seq + 1) if (seq is not None) else None

                frameBuffer += payload

                if marker == 1:
                    # one complete frame available
                    with self.buffer_lock:
                        # append frame bytes; if deque full, leftmost frames get dropped automatically
                        self.buffer.append(frameBuffer)
                        self.total_frames_received += 1

                        # if buffer was previously empty and this is the first frames we got,
                        # set buffer_start_frame_no accordingly
                        if len(self.buffer) == 1:
                            self.buffer_start_frame_no = self.total_frames_received - 1

                        # if play_index not initialized, set to earliest buffered frame
                        if self.play_index < self.buffer_start_frame_no:
                            self.play_index = self.buffer_start_frame_no

                        # if we have prefetched enough frames -> set ready event
                        if len(self.buffer) >= self.PREFETCH_FRAMES:
                            self.video_ready_event.set()
                    frameBuffer = b""

            except socket.timeout:
                # periodic wake: check teardown or continue
                continue
            except Exception:
                # unexpected error -> break to avoid silent thread death
                break

        # cleanup
        try:
            self.rtpSocket.close()
        except:
            pass

    # ---------------- disk write and GUI update ----------------
    def writeFrame(self, data):
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        try:
            with open(cachename, "wb") as f:
                f.write(data)
            return cachename
        except Exception as e:
            print("writeFrame error:", e)
            return None

    def updateMovie(self, imageFile):
        if not imageFile:
            return
        try:
            # defensive check
            if not os.path.exists(imageFile):
                return
            photo = ImageTk.PhotoImage(Image.open(imageFile))
            self.label.configure(image=photo, height=500)
            self.label.image = photo
        except Exception as e:
            print("updateMovie error:", e)

    # ---------------- RTSP connection and requests ----------------
    def connectToServer(self):
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except Exception:
            tkinter.messagebox.showwarning('Connection Failed', f'Connection to "{self.serverAddr}" failed.')

    def sendRtspRequest(self, requestCode):
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply, daemon=True).start()
            self.rtspSeq += 1
            request = (
                f"SETUP {self.fileName} RTSP/1.0\n"
                f"CSeq: {self.rtspSeq}\n"
                f"Transport: RTP/UDP; client_port= {self.rtpPort}\n"
            )
            self.requestSent = self.SETUP

        elif requestCode == self.PLAY and self.state in (self.READY, self.PLAYING):
            self.rtspSeq += 1
            request = (
                f"PLAY {self.fileName} RTSP/1.0\n"
                f"CSeq: {self.rtspSeq}\n"
                f"Session: {self.sessionId}\n"
            )
            self.requestSent = self.PLAY

        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            self.rtspSeq += 1
            request = (
                f"PAUSE {self.fileName} RTSP/1.0\n"
                f"CSeq: {self.rtspSeq}\n"
                f"Session: {self.sessionId}\n"
            )
            self.requestSent = self.PAUSE

        elif requestCode == self.TEARDOWN and self.state != self.INIT:
            self.rtspSeq += 1
            request = (
                f"TEARDOWN {self.fileName} RTSP/1.0\n"
                f"CSeq: {self.rtspSeq}\n"
                f"Session: {self.sessionId}\n"
            )
            self.requestSent = self.TEARDOWN
        else:
            return

        try:
            self.rtspSocket.send(request.encode())
        except Exception:
            print("Failed to send RTSP request.")

        print("\nData sent:\n" + request)

    def recvRtspReply(self):
        while True:
            try:
                reply = self.rtspSocket.recv(1024)
            except:
                reply = None

            if reply:
                try:
                    self.parseRtspReply(reply.decode())
                except Exception as e:
                    print("parseRtspReply error:", e)

            if self.requestSent == self.TEARDOWN:
                try:
                    self.rtspSocket.shutdown(socket.SHUT_RDWR)
                    self.rtspSocket.close()
                except:
                    pass
                break

    def parseRtspReply(self, data):
        lines = data.split("\n")

        try:
            seqNum = int(lines[1].split(" ")[1])
        except:
            return

        if seqNum == self.rtspSeq:
            try:
                session = int(lines[2].split(" ")[1])
            except:
                session = 0

            if self.sessionId == 0:
                self.sessionId = session

            code = int(lines[0].split(" ")[1])

            if code == 200:
                if self.requestSent == self.SETUP:
                    self.state = self.READY
                    self.openRtpPort()
                    self.status_var.set("State: READY")

                elif self.requestSent == self.PLAY:
                    self.state = self.PLAYING
                    self.status_var.set("State: PLAYING")

                elif self.requestSent == self.PAUSE:
                    self.state = self.READY
                    self.status_var.set("State: PAUSE")

                elif self.requestSent == self.TEARDOWN:
                    self.state = self.INIT
                    self.teardownAcked = 1
                    self.status_var.set("State: INIT")

    def openRtpPort(self):
        # socket created in listenRtp to avoid race on re-bind; this method left for compatibility
        pass

    # ---------------- handler for close ----------------
    def handler(self):
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Are you sure?"):
            self.exitClient()
        else:
            self.playMovie()

    # ---------------- main renderer ----------------
    def renderVideo(self):
        """
        Renderer thread:
        - Waits for video_ready_event (buffer prefetch) before showing frames.
        - Uses play_event to pause/resume smoothly.
        - Reads from buffer with lock and writes to cache file temporarily for ImageTk.
        """
        frame_duration = 1.0 / max(1, self.FRAME_RATE)
        while True:
            # exit condition: app closed
            if self.stop_receive.is_set() and not self.play_event.is_set():
                # ensure we close when teardown called
                break

            # Wait until user pressed play
            if not self.play_event.wait(timeout=0.1):
                continue

            # Wait until buffer has enough prefetched frames
            if not self.video_ready_event.wait(timeout=0.1):
                # still buffering
                self.status_var.set("Buffering...")
                time.sleep(0.05)
                continue

            # compute local index inside buffer for current play_index
            with self.buffer_lock:
                buffer_start = self.buffer_start_frame_no
                buffer_len = len(self.buffer)
                buffer_end = buffer_start + buffer_len - 1

                # if play_index is outside current buffer, clamp to available range
                if self.play_index < buffer_start:
                    self.play_index = buffer_start
                if self.play_index > buffer_end:
                    # not yet received frames to show; wait a bit
                    self.video_ready_event.clear()  # request more buffering
                    time.sleep(0.02)
                    continue

                local_idx = self.play_index - buffer_start
                try:
                    frameBytes = self.buffer[local_idx]
                except IndexError:
                    # rare race -> skip iteration
                    time.sleep(0.01)
                    continue

            # write to temp file and update GUI
            imageFile = self.writeFrame(frameBytes)
            if imageFile:
                self.updateMovie(imageFile)

            # advance play_index
            with self.buffer_lock:
                self.play_index += 1
                # if we've consumed most of the buffer, clear video_ready_event so we wait for refill
                if len(self.buffer) - (self.play_index - self.buffer_start_frame_no) < self.PREFETCH_FRAMES // 2:
                    # buffer low
                    self.video_ready_event.clear()

            time.sleep(frame_duration)

