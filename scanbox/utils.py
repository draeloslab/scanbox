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
               motors = dict(knobby_version = 2,
                             knobby_port = None,
                             motors_port = None,
                             motors_baudrate = 57600),
               twophoton = dict(resonant_frequency = 8000,
                                laser_frequency = 80000000,
                                unidirectional = True,
                                triggered_acquisition = False,
                                pmt_acquisition_range = [-1, 1],
                                acquisition_trigger_level = 160,
                                acquisition_trigger_slope = 'positive',
                                acquisition_nbuffers  = 16,
                                margin = 20,
                                bidi_shift = 0,
                                hsync_sign = 1,
                                gain_galvo = np.round(np.logspace(np.log10(1),
                                                                  np.log10(8),
                                                                  13),3).tolist(),
                                gain_resonant_multiplier = 1.42,
                                dv_galvo = 64,
                                warmup_delay = 0.05,
                                sync_pulse_width = 0.002,
                                objectives = ['Nikon 16x/0.8w/WD3.0']),
               cameras = dict(one_photon = dict(driver = 'baesler',
                                                exposure = 0.1)),
               network_cmd_server = 7001, 
               data_path = pjoin(os.path.expanduser('~'),'2pdata'),
               )

def save_config(preferences, user = 'default'):
    preferencepath = pjoin(os.path.expanduser('~'),'scanbox',user)
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
    preferencepath = pjoin(os.path.expanduser('~'),'scanbox',user)

    if not os.path.exists(preferencepath):
        if no_create:
            return None
        os.makedirs(preferencepath)
        print('Creating user folder [{0}]'.format(preferencepath))
    preffile = pjoin(preferencepath,'config.yaml')
    if not os.path.isfile(preffile):
        save_config(DEFAULT,user = user)
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
