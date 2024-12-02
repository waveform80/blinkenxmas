import os
import sys
import tempfile
from queue import Queue
from pathlib import Path
from shutil import copyfile

# NOTE: The fallback comes first here as Python 3.7 incorporates
# importlib.resources but at a version incompatible with our requirements.
# Ultimately the try clause should be removed in favour of the except clause
# once compatibility moves beyond Python 3.9
try:
    import importlib_resources as resources
except ImportError:
    from importlib import resources

from serial.tools import list_ports
# NOTE: The mpremote SerialTransport API is in flux. Currently it's call
# compatible with the old Pyboard interface, but no guarantees for the future.
# We may wind up having to shim this or requiring a base version of mpremote
try:
    from mpremote.transport_serial import SerialTransport
except ImportError:
    from mpremote.pyboard import Pyboard as SerialTransport

from .config import get_config, get_parser, get_pico_config


def default_port():
    """
    Attempts to determine the serial port on which the Pico is connected.
    """
    for port in list_ports.comports():
        if port.vid is not None and port.pid is not None:
            return port.device


def get_flash_parser(config):
    """
    Return an :class:`~blinkenxmas.config.ConfigArgumentParser` instance for
    handling the options of :program:`bxflash`.
    """
    parser = get_parser(config, description=__doc__)

    parser.add_argument(
        'port', type=Path, default=default_port(), nargs='?',
        help="The port to which the Pico is connected. Default: %(default)s")

    parser.set_defaults_from(config)
    return parser


def main(args=None):
    "Entry point for :program:`bxflash`."
    try:
        config = get_config()
        options = get_flash_parser(config).parse_args(args)
        if not options.port.is_char_device():
            raise RuntimeError('serial port is not a character device')

        board = SerialTransport(str(options.port), baudrate=115200)
        try:
            board.enter_raw_repl()
            try:
                with tempfile.TemporaryDirectory() as tmp_name:
                    tmp_path = Path(tmp_name)
                    pico = resources.files('blinkenxmas.pico')
                    for file in pico.iterdir():
                        if not file.is_file():
                            continue
                        if file.name == '__init__.py':
                            continue
                        if file.suffix != '.py':
                            continue
                        copyfile(file, tmp_path / file.name)
                    (tmp_path / 'config.py').write_text(get_pico_config(config))
                    for file in tmp_path.iterdir():
                        print(f'Copying {file.name}')
                        board.fs_put(str(file), file.name)
            finally:
                if board.in_raw_repl:
                    board.exit_raw_repl()
        finally:
            board.close()

    except KeyboardInterrupt:
        print('Interrupted', file=sys.stderr)
        return 2
    except Exception as e:
        debug = int(os.environ.get('DEBUG', '0'))
        if not debug:
            print(str(e), file=sys.stderr)
            return 1
        elif debug == 1:
            raise
        else:
            import pdb
            pdb.post_mortem()
    else:
        return 0
