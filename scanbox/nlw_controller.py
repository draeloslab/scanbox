import serial
import time
from multiprocessing import Process,Queue,Value
from ctypes import c_char_p,c_longdouble, c_long, c_float
import struct
import csv

SET_CONT_RESONANT = '34'
class cmd_msg(ctypes.Structure):
    _fields_ = [('cmd',ctypes.c_uint),
                ('field',ctypes.c_uint),
                ('val',ctypes.c_uint)]
    def make(cmd,field = 0, val = 0):
        res = cmd_msg()
        res.cmd = int(cmd,16)
        res.field = field
        res.val = val
        return res

BOX_DEFAULT_PREFERENCES = dict(continuous_resonant = False)

class BoxController(Process):
    def __init__(self, master_port = 'COM8',
                 baudrate = 115200,
                 log_queue = None,
                 timeout = 0.1, preferences = None):
        super(BoxController,self).__init__()
        self.cmd_queue = Queue()
        self.log_queue = log_queue # this is only needed when saving

        # Events to control the flow of the process
        self.exit = Event()                 # quit the controller
        self.experiment_running = Event()   # quit an experiment

        self.experiment_start = Value(c_longdouble, time.time())
        self.preferences = preferences
        if self.preferences is None:
            self.preferences = dict()
        for f in BOX_DEFAULT_PREFERENCES.keys():
            if not f in self.preferences.keys():
                self.preferences[f] = BOX_DEFAULT_PREFERENCES[f]
        self._status = dict(continuous_resonant = Value('i',0))

    def __init__(self):
        self.set_continuous_resonant(self._status['continuous_resonant'].value)

    def set_continuous_resonant(self,value = False):
        cmd = cmd_msg.make(SET_CONT_RESONANT, val = value)
        self._status['continuous_resonant'].value = value
        self.cmd_queue.put(cmd)

    def usb_write(self, data):
        self.usb.write()

    def run():
        self.usb = serial.Serial(port=self.port,
                                 baudrate=self.baudrate,
                                 timeout = self.timeout)
        self.usb.flushInput()
        self.usb.flushOutput()
        time.sleep(0.5)
        
    while not self.exit.is_set():
        if not self.cmd_queue
