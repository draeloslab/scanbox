import serial
import time
from threading import Thread
from multiprocessing import Queue
import ctypes 
import struct
from .utils import *
CONT_RESONANT = '34'
BIDIRECTIONAL = 34
UNIDIRECTIONAL = 33
MAG = 3
LINESCAN_MODE = '35'
AXIS_GAIN = 51
AXIS_GAIN_CODE = 'f0'
ACQ_CONTROL = 4
RESET = 255
SHUTTER = 16

class cmd_msg(ctypes.Structure):
    _fields_ = [('cmd',ctypes.c_uint),
                ('selector',ctypes.c_uint),
                ('value',ctypes.c_uint)]
    def make(cmd,selector = 0, value = 0):
        res = cmd_msg()
        if type(cmd) is str:
            cmd = int(cmd,16)
        res.cmd = cmd
        res.selector = selector
        res.value = value
        return bytearray(res)

BOX_DEFAULT_PREFERENCES = dict(continuous_resonant = False)

class BoxController(Thread):
    def __init__(self, master_port,
                 baudrate = 115200,
                 log_queue = None,
                 timeout = 0.1, preferences = None):
        super(BoxController,self).__init__()
        self.master_port = master_port
        self.baudrate = baudrate
        self.timeout = timeout
        self.usb = None
        self.connect_usb()
        
        self.cmd_queue = Queue() # use a queue to manage commands
        self.log_queue = log_queue # this is only needed when saving

        # Events to control the flow of the process
        self.exit_flag = False              # quit the controller

        self.preferences = preferences
        self.initialize_settings()
        self.start()

    def connect_usb(self):
        try:
            self.usb = serial.Serial(port=self.master_port,
                                     baudrate=self.baudrate,
                                     timeout = self.timeout)
        except Exception as err:
            display('Could not connect to box on {0}'.format(self.master_port))
            print(err)
            raise(OSError('Could not connect to Neurolabware Control Box'))

    def run(self):
        if self.usb is None:
            self.connect_usb()
        self.usb.flushInput()
        self.usb.flushOutput()
        time.sleep(0.5)
        while not self.exit_flag:
            if not self.cmd_queue.empty():
                cmd = self.cmd_queue.get()
                print(cmd)
                self.usb_write(cmd)
            while self.usb.inWaiting():
                print(self.usb.readline())
    def initialize_settings(self):
        if self.preferences is None:
            self.preferences = dict()
        for f in BOX_DEFAULT_PREFERENCES.keys():
            if not f in self.preferences.keys():
                self.preferences[f] = BOX_DEFAULT_PREFERENCES[f]
        self._status = dict(continuous_resonant = self.preferences['continuous_resonant'])
        #self.set_continuous_resonant(self._status['continuous_resonant'])

    def set_axis_gain(self, axis = 0, x = 0, multiplier = 1):
        '''
        Set the gain of the "x" axis (0) or the "y" axis (1)
        x is 0, 1 or 2 (x1, x2 x4)
        TODO: DOcument this.
        '''
        if axis:
            code = int(AXIS_GAIN_CODE,16) + int(x,16)
        else:
            code = x
        m = np.round((multiplier-1)*128 + 128)
        cmd = cmd_msg.make(AXIS_GAIN, selector = code, value = m)
        # Set variables here.
        self.cmd_queue.put(cmd)

    def start_scan(self):
        cmd = cmd_msg.make(ACQ_CONTROL, value = 1)
        self.cmd_queue.put(cmd)

    def reset_bootloader(self):
        cmd = cmd_msg.make(RESET)
        self.cmd_queue.put(cmd)

    def abort_scan(self):
        cmd = cmd_msg.make(ACQ_CONTROL, value = 0)
        self.cmd_queue.put(cmd)

    def set_shutter(self,value):
        cmd = cmd_msg.make(SHUTTER,value = value)
        self.cmd_queue.put(cmd)
        
    def set_mode(self,mode = 'unidirectional' ):
        if mode in [1, 'bidirectional','bidi']:
            cmd = cmd_msg.make(BIDIRECTIONAL)
        else:
            cmd = cmd_msg.make(UNIDIRECTIONAL)
        self.cmd_queue.put(cmd)
            
    def set_mag(self, magnification):
        cmd = cmd_msg.make(MAG, value = magnification)
        self.cmd_queue.put(cmd)

    def set_linescan_mode(self, mode):
        '''
        Linescan mode 
            0 - unidirectional
            1 - bidirectional
        '''
        if mode in [1, 'bidirectional','bidi']:
            mode = 1
        else:
            mode = 0
        cmd = cmd_msg.make(LINESCAN_MODE, value = mode)
        self.cmd_queue.put(cmd)    

    def set_continuous_resonant(self,value = False):
        cmd = cmd_msg.make(CONT_RESONANT, value = value)
        self._status['continuous_resonant'] = value
        self.cmd_queue.put(cmd)

    def usb_write(self, data):
        self.usb.write(data)

