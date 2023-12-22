import io
import sys
import tempfile

if sys.version_info < (3, 11):
    class SpooledTemporaryFile(tempfile.SpooledTemporaryFile, io.IOBase):
        def readable(self):
            return self._file.readable()

        def read1(self, *args):
            return self._file.read1(*args)

        def readinto(self, b):
            return self._file.readinto(b)

        def readinto1(self, b):
            return self._file.readinto1(b)

        def seekable(self):
            return self._file.seekable()

        def truncate(self, size=None):
            if size is None:
                return self._file.truncate()
            else:
                if size > self._max_size:
                    self.rollover()
                return self._file.truncate(size)

        def writable(self):
            return self._file.writable()

        def detach(self):
            return self._file.detach()
else:
    SpooledTemporaryFile = tempfile.SpooledTemporaryFile
