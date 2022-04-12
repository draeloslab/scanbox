import serial
import time
from threading import Thread
from multiprocessing import Array
import ctypes

TMCL_CMD = dict(ROR  = 1,     # Documentation missing here
                ROL  = 2,
                MST  = 3,
                MVP  = 4,
                SAP  = 5,
                GAP  = 6,
                STAP = 7,
                RSAP = 8,
                SGP  = 9,
                GGP  = 10,
                STGP = 11,
                RSGP = 12,
                RFS  = 13,
                SIO  = 14,
                GIO  = 15,
                SCO  = 30,
                GCO  = 31,
                CCO  = 32,
                STP  = 128,
                RUN  = 129,
                GAS  = 135,
                KBY  = 200)

KNOBBY_MODES = dict(NOP = 0,   # Normal operation
                    ALIGN = 1,
                    TRACK = 2,
                    INIT = 3)

class KnobbyController(Thread):
    def __init__(self, motors_port,
                 knobby_port = None,
                 knobby_version = 2,
                 motors_baudrate = 57600,
                 knobby_baudrate = 57600,
                 log_queue = None,
                 reset_on_start = True,
                 timeout = 1, preferences = None , **kwargs):
        super(KnobbyController,self).__init__()
        self.motor_port = motor_port
        self.motor_baudrate = motor_baudrate
        self.knobby_port = knobby_port
        self.timeout = timeout
        self.motor_usb = None
        self.reset_on_start = reset_on_start
        self.nmotors = 4
        # position arrays
        self.pos_origin_buffer = Array(np.int32, [1,0,0,0,0])
        self.pos_current_buffer = Array(np.int32, [1,0,0,0,0])
        self.pos_origin = np.frombuffer(self.pos_origin_buffer.get_obj(),dtype = np.int32)
        self.pos_current = np.frombuffer(self.pos_current_buffer.get_obj(),dtype = np.int32)

        self._connect_motor()
        if not self.knobby_port is None:
            self._connect_knobby()

        # init sequence        
        self.motor_write('STP') # stop application
        self.set_mode('INIT')   # enable emergency stop
        for m in range(self.nmotors):
            # set actual and target positions to zero
            self.motor_write('SAP', 0, m, 0)
            self.motor_write('SAP', 1, m, 0)
        self.update_origin(self.nmotors)

        if self.reset_on_start:
            # set velocity and acceleration parameters
            for m in range(self.nmotors):
                self.motor_write('SCO', 10, m, self.origin[m+1]) # coordinate 10 to the initial value for each motor
                self.motor_write('SAP', 4, m, 2000)  # max velocity and acceleration
                self.motor_write('SAP', 5, m, 2000)
                self.motor_write('SAP', 6, m, 128)   # max current and standby
                self.motor_write('SAP', 7, m, 16)    # ensure microsteps
                self.motor_write('SAP', 140, m, 6)    
        self.set_mode('NOP')
        self.exit_flag = False      # quit the controller
        
    def update_origin(self, N ):
        self.set_mode('NOP')
        for m in range(N):
            self.motor_write('MST', 0, m, 0) # stop motor
            r = self.motor_write('GAP', 1, m, 0)
            self.pos_origin[m+1] = r[4]
            if self.reset_on_start:
                self.pos_current[m+1] = r[4]
                r = self.motor_write('SCO', 10, m, r[4]) # make stored coords match
                
    def set_mode(self,mode = 'NOP'):
        if self.mode in KNOBBY_MODES:
            self.mode = mode
            self.motor_write('RUN',1,0,KNOBBY_MODES[mode]

    def update_origin(self):
        if self.reset_on_start:
            self.motor_write('RUN',1,0,0)
            
    def motor_write(self, command, cmd_type = 0, motor = 0, value = 0):
        ''' Send command to motor controller and read response. '''
        Tx = bytearray(9)
        if value < 0:
	    value += 4294967296
        Tx[0] = 1
        Tx[1] = TMCL_CMD[command]
        Tx[2] = cmd_type
        Tx[3] = motor
        for i in range(0,4):	                # compute each byte from value 
	    Tx[7-i] = (value>>(8*i)) & 0x0ff
        Tx[8] = sum(Tx[0:8]) & 0x0ff            # checksum
        self.motor_usb.write(Tx)
        r = bytearray(self.motor_usb.read(9))   # wait for response
        return struct.unpack('>BBBBlB',r)
    
    def _connect_motor(self):
        try:
            self.motor_usb = serial.Serial(port = self.motor_port,
                                           baudrate = self.motor_baudrate,
                                           timeout = self.timeout)
        except Exception as err:
            display('Could not connect motors driver on {0}'.format(self.motor_port))
            print(err)
            raise(OSError('Could not connect to Neurolabware Motors Controller'))
        self.motor_usb.reset_output_buffer()
        self.motor_usb.reset_input_buffer()

    def _connect_knobby(self):
        try:
            self.knobby_usb = serial.Serial(port = self.knobby_port,
                                            baudrate = self.knobby_baudrate,
                                            rtscts=True,
                                            dsrdtr=True,
                                            timeout = self.timeout)
        except Exception as err:
            display('Could not connect motors driver on {0}'.format(self.knobby_port))
            print(err)
            raise(OSError('Could not connect to Neurolabware Motors Controller'))
        self.knobby_usb.reset_output_buffer()
        self.knobby_usb.reset_input_buffer()

    
    def run(self):
        while not self.exit_flag:
            tlastread = time.time() 
            if self.knobby_usb.inWaiting() >= 5:
                cmd = bytearray(self.knobby_usb.read(5))
                tlastread = time.time()
                if cmd[0] < 6: # Update motor positions
                    if self.mode != 'TRACK':
                        self.set_mode('TRACK')
                    motor = cmd[0]
                    coord = unpack('<l',r[-4:])[0] # relative to the origin
		    target = coord + self.pos_origin[motor+1]
		    r = self.motor_write('SCO', 10, motor, target)
                elif cmd[0] == 10: # zero position of 3 first axis
                    self.set_mode('NOP')
                    self.update_origin(3)
                    display('[Motor controller] - updated origin')
                elif cmd[0] == 11: # stop and align objective
                    self.set_mode('NOP')
                    self.motor_write('SAP', 4, 3, 750)  # slow down
                    self.set_mode('ALIGN')
                    status = 1
                    while status>0:
                        res = self.motor_write('GAS', 0, 0, 0)
                        status = (r[4] & 0x0ff000000) >> 24
                    self.motor_write('SAP', 4, 3, 2000)  # back to normal speed
                    display('[Motor controller] - aligned the objective')
                    self.update_origin(4)
                    self.set_mode('TRACK')
                elif cmd[0] == 12: # stop tracking and update origin
                    self.set_mode('NOP')
                    self.update_origin(4)
                elif cmd[0] >= 40: # emergency stop
                    res = self._handle_emergency_stop(cmd)
                    if res:
                        display('[Motor controller] - PANIC - disabled controller.')
                        break
            else:
                if mode in ['TRACK']:
                             if time.time() - tlastread > 0.1 # no message from knobby in a while, stop tracking
                    self.set_mode('NOP')
                    panic = self.motor_write('GGP', 0, 2, 0)
                    if panic[4] == 1:
                        display('[Motor controller] - PANIC - disabled controller.')
                        break
        # handle commands missing here.
                      
    def _handle_emergency_stop(cmd):
        if cmd == 40:
            panic = self.motor_write('GGP', 0, 2, 0)
            if not panic[4] == 1:
                self.motor_write('ROR', 0, 2, 2000)
            else:
                return True
        elif cmd == 41:
            panic = self.motor_write('GGP', 0, 2, 0)
            if not panic[4] == 1:
                self.motor_write('ROL', 0, 2, 2000)
            else:
                return True
        elif cmd == 42:
            panic = self.motor_write('GGP', 0, 2, 0)
            if not panic[4] == 1:
                self.motor_write('ROR', 0, 1, 2000)
            else:
                return True
        elif cmd == 43:
            panic = self.motor_write('GGP', 0, 2, 0)
            if not panic[4] == 1:
                self.motor_write('ROL', 0, 1, 2000)
            else:
                return True
        elif cmd == 44:
            panic = self.motor_write('GGP', 0, 2, 0)
            if not panic[4] == 1:
                self.motor_write('ROR', 0, 0, 1600)
            else:
                return True
        elif cmd == 45:
            panic = self.motor_write('GGP', 0, 2, 0)
            if not panic[4] == 1:
                self.motor_write('ROL', 0, 0, 1600)
            else:
                return True
        elif cmd == 46:
            panic = self.motor_write('GGP', 0, 2, 0)
            if not panic[4] == 1:
                self.motor_write('ROL', 0, 3, 600)
            else:
                return True
        elif cmd == 47:
            panic = self.motor_write('GGP', 0, 2, 0)
            if not panic[4] == 1:
                self.motor_write('ROR', 0, 3, 600)
            else:
                return True
        elif cmd == 46:  # stop all motors
            for m in range(4):
                self.motor_write('MST', 0, m, 0)
            panic = self.motor_write('GGP', 0, 2, 0)
            if panic[4] == 1:
                return True
        return False            
                             
