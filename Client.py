from tkinter import *
import tkinter.messagebox
import socket
import threading
import os
from PIL import Image, ImageTk
<<<<<<< HEAD
from collections import deque
import time
=======
import sys, traceback, time
from collections import deque
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0

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

<<<<<<< HEAD
    # ============================================================
    # INIT
    # ============================================================
=======
    # Buffer settings (tweak as needed)
    FRAME_RATE = 20                   # expected fps (used for timing)
    BUFFER_MAX_FRAMES = 400           # max frames to keep in memory (e.g. 20s if 20fps -> 20s)
    PREFETCH_FRAMES = 40              # buffer fill threshold before starting playback (~2s)
    SOCKET_TIMEOUT = 0.5              # UDP socket timeout

>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0
    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
<<<<<<< HEAD
=======

        # RTSP control/state
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
<<<<<<< HEAD
        self.connectToServer()
        self.frameNbr = 0

        # ============================================================
        # Buffers
        # ============================================================
        self.pastBuffer = deque(maxlen=2000)     # lưu frame đã hiển thị
        self.futureBuffer = deque(maxlen=2000)   # lưu frame tương lai (sẽ preload)
        self.currentFrame = None                 # frame đang hiển thị

        # playback / buffering config
        self.SEEK_RANGE = 50                     # tua ±n frames
        self.BUFFER_MIN = 200                    # số frame cần preload trước khi hiển thị (ban đầu)
        self.isBuffering = False                 # flag: đang preload/re-buffer

        # playback control
        self.playEvent = None
        self.pausedFrame = None                  # frame khi pause

        # ============================================================
        # FPS measurement (server-side)
        # ============================================================
        # track timestamps of completed frames to estimate server FPS
        self.frame_times = deque(maxlen=64)     # store deltas between consecutive complete frames
        self.last_frame_time = None
        self.measured_fps = 20.0                # initial guess fallback
        self.fps_lock = threading.Lock()        # protect measured_fps

        # bounds for renderer sleep
        self.MIN_SLEEP = 0.02   # max 50 fps
        self.MAX_SLEEP = 0.2    # min 5 fps

        # Start renderer thread
        self.startBufferRenderer()


    # ============================================================
    # GUI
    # ============================================================
    def createWidgets(self):
        self.setup = Button(self.master, width=20, padx=3, pady=3, text="Setup", command=self.setupMovie)
        self.setup.grid(row=1, column=0, padx=2, pady=2)

        self.start = Button(self.master, width=20, padx=3, pady=3, text="Play", command=self.playMovie)
        self.start.grid(row=1, column=1, padx=2, pady=2)

        self.pause = Button(self.master, width=20, padx=3, pady=3, text="Pause", command=self.pauseMovie)
        self.pause.grid(row=1, column=2, padx=2, pady=2)

        self.teardown = Button(self.master, width=20, padx=3, pady=3, text="Teardown", command=self.exitClient)
        self.teardown.grid(row=1, column=3, padx=2, pady=2)

        # Nút tua lùi
        self.rewind = Button(self.master, width=20, padx=3, pady=3, text="<< Rewind",
                             command=lambda: self.seekFrames(-self.SEEK_RANGE))
        self.rewind.grid(row=2, column=0, padx=2, pady=2)

        # Nút tua tới
        self.forward = Button(self.master, width=20, padx=3, pady=3, text="Forward >>",
                              command=lambda: self.seekFrames(self.SEEK_RANGE))
        self.forward.grid(row=2, column=1, padx=2, pady=2)

        # Video
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

        # Status
        self.statusLabel = Label(self.master, text="Status: Ready", fg="blue")
        self.statusLabel.grid(row=3, column=0, columnspan=4, pady=5)


    # ============================================================
    # STATUS HELPER
    # ============================================================
    def setStatus(self, text, color="blue"):
        try:
            self.statusLabel.config(text=f"Status: {text}", fg=color)
        except:
            pass


    # ============================================================
    # BUTTON HANDLERS
    # ============================================================
=======

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
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0
    def setupMovie(self):
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def exitClient(self):
<<<<<<< HEAD
        # send TEARDOWN then exit
        if self.state != self.INIT:
            try:
                # send TEARDOWN; do not force-close socket here — wait for reply or timeout
                self.sendRtspRequest(self.TEARDOWN)
            except:
                pass

            # wait briefly for teardown acknowledgement (but do not block GUI long)
            wait_until = time.time() + 2.0  # 2 seconds max wait
            while time.time() < wait_until and self.teardownAcked == 0:
                time.sleep(0.01)

        try:
            # try to close RTP socket
            if hasattr(self, 'rtpSocket') and self.rtpSocket is not None:
                try:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                try:
                    self.rtpSocket.close()
                except:
                    pass
        except:
            pass

        # try to close RTSP socket if still open
        try:
            if hasattr(self, 'rtspSocket') and self.rtspSocket is not None:
                try:
                    self.rtspSocket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                try:
                    self.rtspSocket.close()
                except:
                    pass
        except:
            pass

        self.master.destroy()
=======
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
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0

        try:
            os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)
        except:
            pass

<<<<<<< HEAD
    def pauseMovie(self):
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)
            # set playEvent so listener loop can detect and exit if necessary
            if hasattr(self, 'playEvent') and self.playEvent is not None:
                self.playEvent.set()

    def playMovie(self):
        # Play flow with preload:
        # 1) start RTP listener so incoming packets fill futureBuffer
        # 2) send PLAY request to server (server will start streaming)
        # 3) set isBuffering True and wait until futureBuffer >= BUFFER_MIN
        # 4) set isBuffering False -> renderer will start rendering
        if self.state == self.READY:
            # start listener thread (it tolerates being started multiple times as long as socket exists)
            threading.Thread(target=self.listenRtp, daemon=True).start()

            # create playEvent for listener to check stoppage
            self.playEvent = threading.Event()
            self.playEvent.clear()

            # send PLAY to server (server should start sending RTP)
            self.sendRtspRequest(self.PLAY)

            # start buffering phase
            self.isBuffering = True
            self.setStatus(f"Buffering... (0/{self.BUFFER_MIN})", "orange")

            # wait until futureBuffer has enough frames or teardown/paused
            while len(self.futureBuffer) < self.BUFFER_MIN and self.state != self.INIT and self.teardownAcked == 0:
                # update status occasionally
                self.setStatus(f"Buffering... ({len(self.futureBuffer)}/{self.BUFFER_MIN})", "orange")
                time.sleep(0.01)

            # if we ended up tearing down or session closed, do nothing
            if self.teardownAcked == 1 or self.state == self.INIT:
                self.isBuffering = False
                return

            # buffer filled (or server long-sent frames) -> turn off buffering, renderer will start showing frames
            self.isBuffering = False
            self.setStatus("Start playing", "green")

            # ensure state is PLAYING (parseRtspReply may have already set it)
            self.state = self.PLAYING


    # ============================================================
    # RTP LISTENER
    # ============================================================
    def listenRtp(self):
        frameData = b""

        # If rtpSocket isn't open yet, try to open (in case SETUP already called openRtpPort)
        # Usually openRtpPort is called after SETUP reply; keep trying a couple times.
        tries = 0
        while not hasattr(self, 'rtpSocket') and tries < 200:
            time.sleep(0.01)
            tries += 1

        while True:
            try:
                data = self.rtpSocket.recv(20480)
                if data:
                    pkt = RtpPacket()
                    pkt.decode(data)

                    payload = pkt.getPayload()
                    marker = pkt.marker()
                    frameData += payload

                    # Frame hoàn chỉnh (marker==1)
                    if marker == 1:
                        # push into futureBuffer if space, otherwise move to pastBuffer
                        if len(self.futureBuffer) < self.futureBuffer.maxlen:
                            self.futureBuffer.append(frameData)
                        else:
                            # future full: evict oldest from pastBuffer or rotate
                            # keep newest frames: drop the oldest in pastBuffer if possible, then append
                            if len(self.pastBuffer) < self.pastBuffer.maxlen:
                                # if past not full, just move oldest future to past (not ideal), but keep newest in future
                                self.pastBuffer.append(frameData)
                            else:
                                # both full -> drop oldest past, append this to past to avoid losing newest frames
                                try:
                                    self.pastBuffer.popleft()
                                except:
                                    pass
                                self.pastBuffer.append(frameData)

                        # measure server FPS - using timestamp of completed frames
                        now = time.time()
                        if self.last_frame_time is not None:
                            delta = now - self.last_frame_time
                            # ignore obviously bad deltas
                            if 0.001 < delta < 5.0:
                                self.frame_times.append(delta)
                                # compute smoothed average delta
                                avg_delta = sum(self.frame_times) / len(self.frame_times)
                                if avg_delta > 0:
                                    new_fps = 1.0 / avg_delta
                                    # update measured_fps thread-safely
                                    with self.fps_lock:
                                        # clamp a bit to reasonable bounds
                                        if new_fps < 5.0:
                                            self.measured_fps = 5.0
                                        elif new_fps > 60.0:
                                            self.measured_fps = 60.0
                                        else:
                                            self.measured_fps = new_fps
                        self.last_frame_time = now

                        # reset accumulator
                        frameData = b""

            except Exception:
                # if paused or user requested stop -> exit
                if hasattr(self, 'playEvent') and self.playEvent is not None and self.playEvent.isSet():
                    break
                # if teardown acknowledged -> close socket and exit
                if self.teardownAcked == 1:
                    try:
                        if hasattr(self, 'rtpSocket') and self.rtpSocket is not None:
                            try:
                                self.rtpSocket.shutdown(socket.SHUT_RDWR)
                            except:
                                pass
                            try:
                                self.rtpSocket.close()
                            except:
                                pass
                    except:
                        pass
                    break
                # socket timeout or other error -> continue listening
                continue


    # ============================================================
    # TUA FRAME
    # ============================================================
    def seekFrames(self, offset):
        # allow seek when playing or paused (READy or PLAYING). If not playing, refuse.
        if self.state not in (self.PLAYING, self.READY):
            self.setStatus("Cannot seek right now", "red")
            return

        # -----------------------------
        # TUA LÙI
        # -----------------------------
        if offset < 0:
            amount = min(abs(offset), len(self.pastBuffer))

            for _ in range(amount):
                try:
                    frame = self.pastBuffer.pop()
                    # add to left of future so it will be first rendered
                    self.futureBuffer.appendleft(frame)
                except IndexError:
                    break

            self.setStatus(f"Rewind {amount} frames")
            return

        # -----------------------------
        # TUA TỚI
        # -----------------------------
        if offset > 0:
            amount = min(offset, len(self.futureBuffer))

            for _ in range(amount):
                try:
                    frame = self.futureBuffer.popleft()
                    self.pastBuffer.append(frame)
                except IndexError:
                    break

            self.setStatus(f"Forward {amount} frames")
            return


    # ============================================================
    # WRITE FRAME TO FILE + UPDATE UI
    # ============================================================
    def writeFrame(self, data):
        fname = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        try:
            with open(fname, "wb") as f:
                f.write(data)
        except Exception:
            # best effort: ignore write errors
            pass
        return fname

    def updateMovie(self, imageFile):
        try:
            photo = ImageTk.PhotoImage(Image.open(imageFile))
            self.label.configure(image=photo, height=500)
            self.label.image = photo
        except Exception:
            pass


    # ============================================================
    # RTSP PROCESS
    # ============================================================
=======
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
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0
    def connectToServer(self):
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except Exception:
<<<<<<< HEAD
            tkinter.messagebox.showwarning('Connection Failed', f"Cannot connect to {self.serverAddr}")
=======
            tkinter.messagebox.showwarning('Connection Failed', f'Connection to "{self.serverAddr}" failed.')
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0

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
<<<<<<< HEAD

=======
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0
        else:
            return

        try:
            self.rtspSocket.send(request.encode())
        except Exception:
<<<<<<< HEAD
            print("Failed to send RTSP request")

        print("\nSent:\n" + request)

    def recvRtspReply(self):
        # Listener thread for RTSP replies.
        while True:
            try:
                reply = self.rtspSocket.recv(1024)
            except Exception as e:
                # If socket closed or error occurs, exit gracefully
                # If we already got TEARDOWN ack, break quietly
                if self.teardownAcked == 1:
                    break
                # otherwise print debug and break
                print("RTSP receive error:", e)
                break
=======
            print("Failed to send RTSP request.")

        print("\nData sent:\n" + request)

    def recvRtspReply(self):
        while True:
            try:
                reply = self.rtspSocket.recv(1024)
            except:
                reply = None
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0

            if reply:
                try:
                    self.parseRtspReply(reply.decode())
                except Exception as e:
<<<<<<< HEAD
                    print("Failed parsing RTSP reply:", e)

            # If TEARDOWN was requested and acked, close socket and exit
            if self.requestSent == self.TEARDOWN and self.teardownAcked == 1:
                try:
                    if hasattr(self, 'rtspSocket') and self.rtspSocket is not None:
                        try:
                            self.rtspSocket.shutdown(socket.SHUT_RDWR)
                        except:
                            pass
                        try:
                            self.rtspSocket.close()
                        except:
                            pass
=======
                    print("parseRtspReply error:", e)

            if self.requestSent == self.TEARDOWN:
                try:
                    self.rtspSocket.shutdown(socket.SHUT_RDWR)
                    self.rtspSocket.close()
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0
                except:
                    pass
                break

    def parseRtspReply(self, data):
<<<<<<< HEAD
        lines = data.split('\n')

        try:
            seqNum = int(lines[1].split(' ')[1])
        except Exception:
=======
        lines = data.split("\n")

        try:
            seqNum = int(lines[1].split(" ")[1])
        except:
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0
            return

        if seqNum == self.rtspSeq:
            try:
<<<<<<< HEAD
                session = int(lines[2].split(' ')[1])
            except Exception:
=======
                session = int(lines[2].split(" ")[1])
            except:
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0
                session = 0

            if self.sessionId == 0:
                self.sessionId = session

<<<<<<< HEAD
            try:
                code = int(lines[0].split(' ')[1])
            except Exception:
                code = 0
=======
            code = int(lines[0].split(" ")[1])
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0

            if code == 200:
                if self.requestSent == self.SETUP:
                    self.state = self.READY
                    self.openRtpPort()
<<<<<<< HEAD
                    self.clearBuffer()
                    self.setStatus("Setup done – Ready")

                elif self.requestSent == self.PLAY:
                    # server accepted PLAY; keep state playing
                    self.state = self.PLAYING
                    # if we are still buffering, renderer will wait; otherwise start rendering
                    if not self.isBuffering:
                        self.setStatus("Playing")
                    else:
                        self.setStatus("Buffering before play...", "orange")

                elif self.requestSent == self.PAUSE:
                    self.state = self.READY
                    if self.playEvent:
                        self.playEvent.set()
                    self.setStatus("Paused")
                    self.pausedFrame = self.currentFrame
                    if self.pausedFrame:
                        fname = self.writeFrame(self.pausedFrame)
                        self.updateMovie(fname)

                elif self.requestSent == self.TEARDOWN:
                    # Proper teardown: update state, mark ack
                    self.state = self.INIT
                    self.teardownAcked = 1
                    self.clearBuffer()
                    self.setStatus("Closed session", "red")

    
    # ============================================================
    # RTP SOCKET
    # ============================================================
    def openRtpPort(self):
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtpSocket.settimeout(0.5)
        try:
            self.rtpSocket.bind(("", self.rtpPort))
        except Exception:
            tkinter.messagebox.showwarning('Unable to Bind', f"Port {self.rtpPort} cannot bind")


    # ============================================================
    # RENDERING THREAD
    # ============================================================
    def startBufferRenderer(self):
        threading.Thread(target=self.renderVideo, daemon=True).start()

    def renderVideo(self):
        # slight startup delay
        time.sleep(0.01)

        while True:
            # Dừng render khi không PLAYING
            if self.state != self.PLAYING:
                time.sleep(0.01)
                continue

            if self.isBuffering:
                time.sleep(0.01)
                continue

            # If futureBuffer becomes too low during playback -> re-buffer
            if len(self.futureBuffer) < 10:
                # Enter re-buffering mode
                self.setStatus("Re-buffering...", "orange")
                self.isBuffering = True
                # Wait until we have a small safe amount
                while len(self.futureBuffer) < 50 and self.state == self.PLAYING and self.teardownAcked == 0:
                    self.setStatus(f"Re-buffering {len(self.futureBuffer)}/50", "orange")
                    time.sleep(0.01)
                self.isBuffering = False
                # If shutdown occured during buffering, skip rendering
                if self.teardownAcked == 1 or self.state != self.PLAYING:
                    continue

            # Normal playback
            if len(self.futureBuffer) == 0:
                # nothing to play (should be rare due to buffering strategy)
                self.setStatus("Buffer empty...", "orange")
                time.sleep(0.01)
                continue

            self.setStatus(f"Playing (past={len(self.pastBuffer)} future={len(self.futureBuffer)})")

            # Read measured fps thread-safely
            with self.fps_lock:
                fps = self.measured_fps
            # clamp sleep
            sleep_time = 1.0 / fps if fps > 0 else self.MIN_SLEEP
            if sleep_time < self.MIN_SLEEP:
                sleep_time = self.MIN_SLEEP
            if sleep_time > self.MAX_SLEEP:
                sleep_time = self.MAX_SLEEP

            # Frame mới (try-popleft safely)
            try:
                self.currentFrame = self.futureBuffer.popleft()
            except IndexError:
                # race condition: empty
                time.sleep(0.001)
                continue

            # push to pastBuffer for rewind feature
            self.pastBuffer.append(self.currentFrame)

            # Render frame
            img = self.writeFrame(self.currentFrame)
            self.updateMovie(img)

            # playback framerate control: sync to measured server fps
            time.sleep(sleep_time)


    # ============================================================
    # CLEAR BUFFER
    # ============================================================
    def clearBuffer(self):
        try:
            self.pastBuffer.clear()
            self.futureBuffer.clear()
            self.currentFrame = None
            self.setStatus("Buffer cleared")
        except Exception:
            pass


    # ============================================================
    # Closing handler
    # ============================================================
    def handler(self):
        # pause, ask confirmation, then teardown
=======
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
>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Are you sure?"):
            self.exitClient()
        else:
<<<<<<< HEAD
            # if user cancels quitting, resume playing if appropriate
            if self.state == self.READY:
                # do nothing
                pass
            elif self.state == self.PLAYING:
                try:
                    # restart play if needed
                    self.playMovie()
                except:
                    pass
=======
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

>>>>>>> 9913b311f97b74c5aea06befc3493a54d7cb8db0
