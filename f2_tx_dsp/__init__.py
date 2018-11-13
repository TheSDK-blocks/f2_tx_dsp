# f2_dsp class 
# Last modification by Marko Kosunen, marko.kosunen@aalto.fi, 12.11.2018 15:09
import numpy as np
import pandas as pd
import scipy.signal as sig
import tempfile
import subprocess
import shlex
import time

from thesdk import *
from verilog import *
from f2_util_classes import *
import signal_generator_802_11n as sg80211n


class f2_tx_dsp(verilog,thesdk):
    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self,*arg): 
        self.proplist = [ 'Rs', 'Rs_dsp', 'Txbits', 'Users' ];    #properties that can be propagated from parent
        self.Rs = 160e6;                 # sampling frequency
        self.Rs_dsp=20e6
        #These are fixed
        self.Txantennas=4
        self.Txbits=9
        self.Users=4                     #This is currently fixed by implementation
        #Matrix of [Users,time,1]
        self.model='sv';                  #can be set externally, but is not propagated
        self.par= False                  #by default, no parallel processing

        self.queue= []                   #by default, no parallel processing
        self.DEBUG= False
        if len(arg)>=1:
            parent=arg[0]
            self.copy_propval(parent,self.proplist)
            self.parent =parent;

        self.iptr_A = iofifosigs(**{'users':self.Users})

        self._Z_real_t=[ refptr() for i in range(self.Txantennas) ]
        self._Z_real_b=[ refptr() for i in range(self.Txantennas) ]
        self._Z_imag_t=[ refptr() for i in range(self.Txantennas) ]
        self._Z_imag_b=[ refptr() for i in range(self.Txantennas) ]

        self.init()
    
    def init(self):
        self.def_verilog()
        self._vlogmodulefiles =list(['clkdiv_n_2_4_8.v', 'AsyncResetReg.v'])

        #Here's how we sim't for the tapeout
        self._vlogparameters=dict([ ('g_Rs_high',self.Rs), ('g_Rs_low',self.Rs_dsp), 
            ('g_shift'            , 0),
            ('g_scale0'           , 8),
            ('g_scale1'           , 2),
            ('g_scale2'           , 2),
            ('g_scale3'           , 512),
            ('g_cic3shift'        , 4),
            ('g_user_spread_mode' , 0),
            ('g_user_sum_mode'    , 0),
            ('g_user_select_index', 0),
            ('g_interpolator_mode', 4),
            ('g_dac_data_mode'   , 6)
            ])
        
    def run(self,*arg):
        if len(arg)>0:
            self.par=True      #flag for parallel processing
            self.queue=arg[0]  #multiprocessing.queue as the first argument
        if self.model=='py':
            self.process_input()
        elif self.model=='sv':
            self.write_infile()
            #Object to have handle for it in other methods
            #Should be handled with a selector method using 'file' attribute
            a=verilog_iofile(self,**{'name':'Z'})
            a.simparam='-g g_outfile='+a.file
            self.run_verilog()
            self.read_outfile()
            [ _.remove() for _ in self.iofiles ]
    def process_input(self):
        self.print_log({'type':"F", 'msg':"Python model not yet implemented"}) 

    def write_infile(self,**kwargs):
        for i in range(self.Users):
            if i==0:
                indata=self.iptr_A.data[i].udata.Value.reshape(-1,1)
            else:
                indata=np.r_['1',indata,self.iptr_A.data[i].udata.Value.reshape(-1,1)]
        if self.model=='sv':
            #This adds an iofile to self.iiofiles list
            a=verilog_iofile(self,**{'name':'A','data':indata})
            print(self.iofiles)
            a.simparam='-g g_infile='+a.file
            a.write()
            indata=None #Clear variable to save memory
        else:
            pass

    def read_outfile(self):
        #Handle the ofiles here as you see the best
        a=list(filter(lambda x:x.name=='Z',self.iofiles))[0]
        a.read(**{'dtype':'object'})
        for i in range(self.Txantennas):
            self._Z_real_t[i].Value=a.data[:,i*self.Txantennas+0].astype('str').reshape(-1,1)
            self._Z_real_b[i].Value=a.data[:,i*self.Txantennas+1].astype('int').reshape(-1,1)
            self._Z_imag_t[i].Value=a.data[:,i*self.Txantennas+2].astype('str').reshape(-1,1)
            self._Z_imag_b[i].Value=a.data[:,i*self.Txantennas+3].astype('int').reshape(-1,1)

