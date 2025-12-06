class VideoStream:
    def __init__(self, filename):
        self.filename = filename
        try:
            self.file = open(filename, 'rb')
        except:
            raise IOError
        self.frameNum = 0
        
    # def nextFrame(self):
    # 	"""Get next frame."""
    # 	data = self.file.read(5) # Get the framelength from the first 5 bits
    # 	if data: 
    # 		framelength = int(data)
                            
    # 		# Read the current frame
    # 		data = self.file.read(framelength)
    # 		self.frameNum += 1
    # 	return data
    def nextFrame(self):
        """Get next frame."""

        current_pos = self.file.tell()
        ## sample mjpeg file
        try:
            header = self.file.read(5)
            if len(header) == 5 and header.isdigit():

                framelength = int(header)
                data = self.file.read(framelength)
                self.frameNum += 1
                return data
        except ValueError:
            pass
        ## standard mjpeg file
        self.file.seek(current_pos)
        
        data = b''

        while True:
            chunk = self.file.read(4096)
            if not chunk:
                break         
            data += chunk
            end_marker = b'\xff\xd9'
            eoi_pos = data.find(end_marker)
            
            if eoi_pos != -1:
                frame_end = eoi_pos + 2 
                frame_data = data[:frame_end]
        
                next_frame_pos = current_pos + frame_end
                self.file.seek(next_frame_pos)
                
                self.frameNum += 1
                return frame_data

        return None
    def frameNbr(self):
        """Get frame number."""
        return self.frameNum