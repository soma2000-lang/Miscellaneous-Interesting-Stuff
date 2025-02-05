class BufferedFile:
    def __init__(self, file_obj, buffer_size):
        """
        Initialize BufferedFile with a file object and buffer size in bytes.
        
        Args:
            file_obj: A file object opened in binary write mode ('wb')
            buffer_size: Maximum size of the buffer in bytes
        """
        if not file_obj.writable():
            raise ValueError("File object must be writable")
        if buffer_size <= 0:
            raise ValueError("Buffer size must be positive")
            
        self._file = file_obj
        self._buffer_size = buffer_size
        self._buffer = bytearray()
        
    def write(self, data):
        """
        Write data to the buffer, flushing to disk if buffer becomes full.
        
        Args:
            data: Bytes or bytearray to write
            
        Returns:
            Number of bytes written
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("Data must be bytes or bytearray")
            
        # Convert to bytearray if needed
        data = bytearray(data)
        bytes_to_write = len(data)
        bytes_written = 0
        
        while bytes_written < bytes_to_write:
            # Calculate how many bytes we can add to buffer
            space_in_buffer = self._buffer_size - len(self._buffer)
            chunk_size = min(space_in_buffer, bytes_to_write - bytes_written)
            
            # Add chunk to buffer
            self._buffer.extend(data[bytes_written:bytes_written + chunk_size])
            bytes_written += chunk_size
            
            # If buffer is full, flush it
            if len(self._buffer) >= self._buffer_size:
                self.flush()
                
        return bytes_written
        
    def flush(self):
        """
        Flush the buffer contents to disk and clear the buffer.
        """
        if self._buffer:
            self._file.write(self._buffer)
            self._file.flush()
            self._buffer.clear()
            
    def close(self):
        """
        Flush any remaining data and close the underlying file.
        """
        self.flush()
        self._file.close()
        
    def __enter__(self):
        """Support for context manager protocol"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure file is properly closed when exiting context"""
        self.close()