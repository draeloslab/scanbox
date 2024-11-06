import serial
import time
from threading import Thread
from multiprocessing import Queue
import ctypes 
import struct
from .utils import *

class ScanboxController(Thread):
    def __init__(self, master_port,
                 slave_port = None,
                 baudrate = 57600,  # 1000000, different from motor_baudrate?
                 log_queue = None,
                 timeout = 1, preferences = None):
        '''
Class to control Neurolabware Scanbox hardware.
        '''
        super(ScanboxController,self).__init__()
        self.master_port = master_port
        self.baudrate = baudrate
        self.timeout = timeout
        self.usb = None
        self.connect_usb()
        self.cmd_queue = Queue()    # use a queue to manage commands
        self.log_queue = log_queue  # this is only needed when saving
        # Events to control the flow of the process
        self.exit_flag = False      # quit the controller
        self.preferences = preferences

        self.pockels_lut = None
        self.resonant_gains = None
        self.galvo_gains = None
        self.pmt_gains = [0 for i in range(4)]
        self.interrupt_mask = None
        self.scanmode = None
        self.initialize_settings()
        #self.start()               # This starts the commands

    def log_msg(self,msg):
        '''Over-write this function to do something when there is need to log'''
        print('[Scanbox] ' + msg)
                
    def connect_usb(self):
        try:
            self.usb = serial.Serial(port = self.master_port,
                                     baudrate = self.baudrate,
                                     xonxoff = True,
                                     timeout = self.timeout)
        except Exception as err:
            display('Could not connect to box on {0}'.format(self.master_port))
            print(err)
            raise(OSError('Could not connect to Neurolabware Control Box'))
        self.usb.reset_output_buffer()
        self.usb.reset_input_buffer()

    def write(self, data):
        self.usb.write(data)
        self.usb.flush()
        
    def run(self):
        while not self.exit_flag:
            if not self.cmd_queue.empty():
                cmd = self.cmd_queue.get()
                print(cmd,flush=True)
                self.write(cmd)
            while self.usb.inWaiting() >= 1:
                print(self.usb.readline(),flush=True)

    def initialize_settings(self):
        if self.preferences is None:
            config = get_config()
            self.preferences = config['twophoton']

        # initialization
        self.get_version()            # get the version
        self.set_lcd_token(1)         # give token to the master ?
        self.set_master_slave(True)   # enable master-slave comms
        self.optotune_active(0)       # disable optotune
        self.current_power_active(0)  # disable link between the optotune and power
        [self.pmt_gain(pmt,0) for pmt in range(4)] # set pmt gains to zero
        self.set_lines(512)           # set the default number of lines
        self.set_nframes(-1)          # number of frames
        self.select_magnification(0)  # choose the default magnification
        self.set_interrupt_mask(3)    # set the interrupt mask

        self.galvo_dv(self.preferences['dv_galvo'])                                        # set galvo dv
        self.mag_gains_y(self.preferences['gain_galvo'])                                   # set galvo gains
        self.mag_gains_x([
            g*self.preferences['gain_resonant_multiplier']
            for g in self.preferences['gain_galvo']]) # set resonant gains

        self.pockels_range()
        self.reset_pockels_lut()

        self.hsync_sign(self.preferences['hsync_sign'])
        self.disable_ttl_trigger()
        self.continuous_resonant(False)
        self.set_warmup_delay(50)  # set to 50??

        self.set_mirror_position(1) # set for 2p

        self.set_pockels(0)
        self.set_deadband_period(np.round(24e6/self.preferences['resonant_frequency']/2)) # matlab deadband which one??
        self.set_deadband(0,0)
        self.set_scanmode(self.preferences['unidirectional']==False)  # why??

        self.galvo_mode(False)
        self.set_galvo(False)

        self.set_onephoton_ttls(False)
        self.box_status_message(0)  # say hi

    def get_version(self):
        ''' Get the firmware version of the master controller '''
        self.write(struct.pack('!BBB',
                               int('78',16),
                               int('aa',16),
                               int('55',16)))
        self.usb.timeout = 2 # set the timeout to 1 sec
        tt = self.usb.read(3) # response is 3 bytes
        tt = struct.unpack("!BBB",tt)
        self.master_version = tt
        self.log_msg('Master version {0}.{1}.{2}'.format(*self.master_version))
        return tt

    def set_lcd_token(self, token = 1):
        # what does this do?
        # TODO: that's my question as well!!
        self.write(struct.pack('!BBB',0,token,0))
        self.log_msg('Setting lcd token: {0}'.format(token))

    def set_master_slave(self, enable = True):
        ''' Enable or disable the master-slave line drive'''
        self.write(struct.pack('!BBB',int('0e',16),enable,0))
        self.log_msg('{0} the master-slave line drive.'.format(
            'Enabled' if enable else 'Disabled'))            


    def optotune_active(self, enable = False):
        ''' Enable/disable the optotunable lens '''
        self.write(struct.pack('!BBB',23,enable,0))
        self.log_msg('{0} the tunable lens (fast-Z).'.format(
            'Enabled' if enable else 'Disabled'))            


    def current_power_active(self, enable = False):
        # enable/disable current power 
        self.write(struct.pack('!BBB',20,enable,0))
        self.log_msg('{0} current power'.format(
            'Enabled' if enable else 'Disabled'))


    def box_status_message(self, message = 1):
        '''
        Messages
           1) Goodbye.
        '''
        self.write(struct.pack('!BBB', 12, message,0))


    def set_interrupt_mask(self, mask):
        self.interrupt_mask = mask
        self.write(struct.pack('!BBB', 64, 0, mask))
        self.log_msg('Set interrupt mask to: {0}.'.format(self.interrupt_mask))
        

    def galvo_dv(self, value = 64):
        self.write(struct.pack('!BBB', int('66',16), value, 0))
        self.log_msg('Setting galvo dv per line to: {0}.'.format(value))

    def galvo_mode(self, value = False):
        ''' Turn the galvo resonant mode ON or OFF'''
        self.write(struct.pack('!BBB', int('ed',16), value, 0))
        self.log_msg('{0} the galvo "resonant" mode.'.format(
            'Enabled' if value else 'Disabled'))

    def set_galvo(self, enable = False):
        ''' Activate or deactivate the galvo '''
        self.write(struct.pack('!BBB', int('eb',16), enable, enable))
        self.log_msg('{0} the galvo.'.format(
            'Enabled' if enable else 'Disabled'))
        
    def mag_gains_x(self, gains = []):
        # gains = np.round(gains,4)  # rounded to 4 decimal, is this even necessary??
        for i,g in enumerate(gains):
            xh = int(np.floor(g))
            xl = int(np.floor((g-xh)*10))
            self.write(struct.pack('!BBB', int('b0',16)+i, xh, xl))
        self.resonant_gains = gains
        self.log_msg('Setting resonant (x) gains to: {0}.'.format(gains))
        
    def mag_gains_y(self, gains = []):
        for i,g in enumerate(gains):
            xh = int(np.floor(g))
            xl = int(np.floor((g-xh)*10))
            self.write(struct.pack('!BBB', int('c0',16)+i, xh, xl))
        self.galvo_gains = gains
        self.log_msg('Setting galvo (y) gains to: {0}.'.format(gains))

        
    def pockels_lut(self, pockels_lut = np.arange(256)):
        self.pockels_lut = pockels_lut
        for i,val in enumerate(pockels_lut):
            self.write(struct.pack('!BBB', int('43',16), i, val))
        self.log_msg('Set the pockels lookup table.')

    def reset_pockels_lut(self):
        self.write(struct.pack('!BBB', int('44',16), 0, 0))
        self.log_msg('Reset the pockels lookup table.')
        
    def pockels_range(self, dac = 1, pga = 2):
        self.write(struct.pack('!BBB', 13, int(dac), int(pga)))
        self.log_msg('Set the pockels range: dac {0} - pga {1}.'.format(dac, pga))

    def hsync_sign(self,sign = 1):
        '''
        Set the horizontal axis sign
           0 - normal
           1 - flip the horizontal axis
        '''
        self.write(struct.pack('!BBB', int('80',16), int(sign), 0))
        self.log_msg('Set the sign of the horizontal axis ({0}).'.format(
            'normal' if sign==0 else 'flipped'))

    def disable_ttl_trigger(self):
        self.write(struct.pack('!BBB', int('e1',16), int('00',16), int('00',16)))
        self.log_msg('Disabled the external trigger.')

    def continuous_resonant(self, enable = False):
        self.write(struct.pack('!BBB', int('34',16), int(enable), 0))
        self.log_msg('{0} the continuous resonant mode'.format(
            'Enabled' if enable else 'Disabled'))

    def set_warmup_delay(self,delay = 50):
        self.warmup_delay = delay
        self.write(struct.pack('!BBB', 11, 0, int(delay)))
        self.log_msg('Set warmup delay to {0}.'.format(delay))

    
    def set_mirror_position(self,position = 0):
        self.mirror_position = position
        self.write(struct.pack('!BBB', 5, 0, int(position)))
        self.log_msg('Mirror position {0}.'.format(position))
    
    def set_pockels(self,active,base=0):
        self.write(struct.pack('!BBB', 8, int(base), int(active*255)))
        self.log_msg('Pockels set: {0} {1}.'.format(base,active))

    def set_deadband_period(self,period):
        '''Sets the period of the deadband pwm which has to be between 1245 and 1500 '''
        period = int(np.clip(period,1245,1500))
        self.deadband_period = period
        self.write(struct.pack('!BBB', 10, 0, 1500-period))
        self.log_msg('Deadband period: {0} .'.format(period))

    def set_deadband(self,left = 0,right = 0):
        self.deadband = [int(left), int(right)]
        self.write(struct.pack('!BBB', 9, int(left), int(right)))
        self.log_msg('Deadband blanking: left - {0} right {1} .'.format(left,right))

    def set_scanmode(self, mode = 'unidirectional'):
        if mode in [0,'uni','unidirectional']:
            self.write(struct.pack('!BBB', 33, 0, 0))
            self.scanmode = 'unidirectional'
        else:
            self.write(struct.pack('!BBB', 34, 0, 0))
            self.scanmode = 'bidirectional'
        self.log_msg('Scanning mode: {0}'.format(self.scanmode))
            
    def get_frame_rate(self):
        return self.resonant_freq/self.nlines*(2-(0 if self.scanmode == 'bidirectional' else 1))

    
    def set_camera_ttl(self,enable = True):
        self.write(struct.pack('!BBB', 121, int(enable), 0))
        self.log_msg('{0} camera ttl'.format(
            'Enabled' if enable else 'Disabled'))

    def set_trigger(self, trigger = 'internal'):
        if trigger in ['internal',0]:
            trigger = 0
        else:
            trigger = 1    
        self.write(struct.pack('!BBB', int('e2',16), int(trigger), 0))
        self.trigger = 'external' if trigger else 'internal'
        self.log_msg('Setting trial start/stop signal to {0}'.format(
            'TTL1' if trigger else 'extension header P1.6'))

    def set_onephoton_ttls(self, enable = False):
        self.write(struct.pack('!BBB', int('f7',16), int(enable), int(enable)))
        self.log_msg('{0} the onephoton camera ttl for the behavior cameras'.format(
            'Enabled' if enable else 'Disabled'))
        
    def select_magnification(self,magnification):
        self.write(struct.pack('!BBB', 3, 0, int(magnification)))
        self.mag_idx = magnification
        self.log_msg('Magnification: {0}'.format(self.mag_idx))

        
    def set_lines(self, nlines = 512):
        #b0,b1 = _encodenumber(nlines)
        self.write(struct.pack('!BH', 2, np.uint16(nlines)))
        self.nlines = int(nlines)
        self.log_msg('Number of lines: {0}'.format(self.nlines))
    
    def set_nframes(self, nframes = 0):
        #b0,b1 = _encodenumber(nframes)
        self.write(struct.pack('!BH', 1, np.uint16(nframes)))
        self.nframes = nframes
        self.log_msg('Number of frames: {0}'.format(self.nframes))

    def abort(self):
        self.write(struct.pack('!BBB', 4, 0, 0))
        self.is_acquiring = False
        # set gains to zero!
        self.log_msg('Stopped scanning.')

    def scan(self):
        self.write(struct.pack('!BBB', 4, 0, 1))
        self.is_acquiring = True
        self.log_msg('Started scanning.')

    def pmt_gain(self,pmt, gain = 0):
        x = np.uint16(gain*3000)
        self.write(struct.pack('!BH', int(6+pmt), x))
        self.pmt_gains[pmt] = gain
        self.log_msg('PMT {0} gain: {1}'.format(pmt,gain))
       
        
def _encodenumber(number):
    '''encodes a number in 2 uint8 to send to scanbox'''
    number = np.uint16(number)
    b0 =  np.shift_left(np.bitwise_and(number,int('ff00',16)),-8)
    b1 =  np.bitwise_and(number,int('00ff',16))
    return b0,b1

        
        
        
