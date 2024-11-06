import sys
import os
from datetime import datetime
import numpy as np
from os.path import join as pjoin
import yaml

def display(msg):
    sys.stdout.write('[{0}] {1}\n'.format(datetime.today().strftime('%y-%m-%d %H:%M:%S'),
                                          msg))
    sys.stdout.flush()


DEFAULT = dict(neurolabware_box=dict(master_port = None,
                                     slave_port = None,
                                     firmware = '4.5'),
               motors = dict(knobby_version = 9,#2,
                             knobby_port = 'COM13',#None,
                             motors_port = 'COM5',#None,
                             motors_baudrate = 57600),
               twophoton = dict(resonant_frequency = 8000,
                                laser_frequency = 80000000,
                                unidirectional = True,
                                triggered_acquisition = False,
                                pmt_acquisition_range = [-1, 1],
                                acquisition_trigger_level = 160,
                                acquisition_trigger_slope = 'positive',  # 0 is positive, do we need to change this?
                                acquisition_nbuffers  = 16,
                                margin = 20,
                                bidi_shift = 0,
                                hsync_sign = 0,  # change to normal 0; originally was 1
                                gain_galvo = np.round(np.logspace(np.log10(1),
                                                                  np.log10(8),
                                                                  13),4).tolist(),  #v
                                gain_resonant_multiplier = 1.0,
                                dv_galvo = 64,  # v
                                warmup_delay = 50,  # what is the unit here?? 0.05
                                sync_pulse_width = 16,  # same, what is the unit? 0.002, is this even the same as camp_pulse_width?
                                objectives = ['Nikon 16x_0.8w_WD3.0']),  # 'Nikon 16x/0.8w/WD3.0'
               cameras = dict(one_photon = dict(cam_id = 0,
                                                driver = 'basler',
                                                exposure = 100,
                                                binning = 4)),
               network_cmd_server = 7001, 
               data_path = pjoin(os.path.expanduser('~'),'2pdata'),
               )

def save_config(preferences, user = 'default'):
    preferencepath = pjoin(os.path.expanduser('~'),'codes','scanbox',user)
    preffile = pjoin(preferencepath,'config.yaml')
    if not os.path.exists(preferencepath):
        os.makedirs(preferencepath)
        print('Creating folder [{0}]'.format(preferencepath))
    with open(preffile, 'w') as outfile:
        yaml.dump(preferences,
                  outfile)
                  #sort_keys = True,
                  #indent = 4)

def get_config(user='default', no_create=False):
    ''' Reads/creates the user preferences from the home directory.

    pref = get_preferences(user)

    Joao Couto - April 2021
    '''
    preferencepath = pjoin(os.path.expanduser('~'),'codes', 'scanbox',user)
    if not os.path.exists(preferencepath):
        if no_create:
            return None
        os.makedirs(preferencepath)
        print('Creating user folder [{0}]'.format(preferencepath))
    preffile = pjoin(preferencepath,'config.yaml')
    # if not os.path.isfile(preffile):
    save_config(DEFAULT,user = user)  # override files nevertheless
    print('Saving default config to: {0} '.format(preffile))
    with open(preffile, 'r') as infile:
        pref = yaml.load(infile, Loader = yaml.FullLoader)
    pref['user'] = user
    pref['config_path'] = preferencepath
    for k in DEFAULT.keys():
        if not k in pref.keys():
            # add default
            pref[k] = DEFAULT[k]
    return pref
