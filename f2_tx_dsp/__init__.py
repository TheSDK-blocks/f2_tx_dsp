# f2_dsp class 
# Last modification by Marko Kosunen, marko.kosunen@aalto.fi, 18.11.2018 14:01
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
from f2_tx_path import *
import signal_generator_802_11n as sg80211n


class f2_tx_dsp(verilog,thesdk):
    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self,*arg): 
        self.proplist = [ 
                'Rs',
                'Rs_dsp', 
                'Txbits', 
                'Users', 
                'dsp_interpolator_scales', 
                'dsp_interpolator_cic3shift' 
                'Txantennas' 
                ];    #properties that can be propagated from parent
        self.Rs = 160e6;                        # sampling frequency
        self.Rs_dsp=20e6
        #These are fixed
        self.Txantennas=4
        self.Txbits=9
        ####
        self.Users=4                           #This is currently fixed by implementation
        self.dsp_interpolator_scales=[8,2,2,512]   #This works with the current hardware
        self.dsp_interpolator_cic3shift=4
        self.dsp_interpolator_mode=''          # If not given, it will be derived
        self.user_sum_mode    = 0              #Wether to sum users or not
        self.user_select_index= 0              #by default, no parallel processing
        self.user_spread_mode = 0
        self.user_sum_mode    = 0
        self.user_select_index= 0
        self.dac_data_mode   = 6
        #Matrix of [Users,time,1]
        self.model='py';                  #can be set externally, but is not propagated
        self.par= False                   #by default, no parallel processing

        self.queue= []                    #by default, no parallel processing
        self.DEBUG= False
        if len(arg)>=1:
            self.parent=arg[0]
            self.copy_propval(self.parent,self.proplist)

        ## Connections should be only a function of propagated parameters
        self.iptr_A = iofifosigs(**{'users':self.Users})
        self._Z_real_t=[ IO() for i in range(self.Txantennas) ]
        self._Z_real_b=[ IO() for i in range(self.Txantennas) ]
        self._Z_imag_t=[ IO() for i in range(self.Txantennas) ]
        self._Z_imag_b=[ IO() for i in range(self.Txantennas) ]

        #Add Tx paths
        self.tx_paths=[ f2_tx_path(self) for i in range(self.Txantennas)]

        # Interpolator calculates the mode absed on the sampling rates.
        # It can be utilized here
        if not self.dsp_interpolator_mode:
            self.dsp_interpolator_mode=self.tx_paths[0].interpolator_mode
        self._vlogmodulefiles =list(['clkdiv_n_2_4_8.v', 'AsyncResetReg.v'])

        # Create connections
        # Currently not needed, all parameters propagated
        for i in range(self.Txantennas):
            for user in range(self.Users):
                self.tx_paths[i].iptr_A[user]=self.iptr_A.data[user].udata
            self._Z_real_t[i]=self.tx_paths[i]._Z_real_t
            self._Z_real_b[i]=self.tx_paths[i]._Z_real_b
            self._Z_imag_t[i]=self.tx_paths[i]._Z_imag_t
            self._Z_imag_b[i]=self.tx_paths[i]._Z_imag_b

        self.init()
    
    def init(self):
        #parent values may have been changed
        self.def_verilog()

        #Here's how we sim't for the tapeout
        self._vlogparameters=dict([ ('g_Rs_high',self.Rs), ('g_Rs_low',self.Rs_dsp), 
            ('g_shift'            , 0                          ),
            ('g_scale0'           , self.dsp_interpolator_scales[0]),
            ('g_scale1'           , self.dsp_interpolator_scales[1]),
            ('g_scale2'           , self.dsp_interpolator_scales[2]),
            ('g_scale3'           , self.dsp_interpolator_scales[3]),
            ('g_cic3shift'        , self.dsp_interpolator_cic3shift),
            ('g_user_spread_mode' , self.user_spread_mode      ),
            ('g_user_sum_mode'    , self.user_sum_mode         ), 
            ('g_user_select_index', self.user_select_index     ),
            ('g_interpolator_mode', self.dsp_interpolator_mode     ),
            ('g_dac_data_mode'    , self.dac_data_mode         ) 
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
        #Could use parallel forloop here
        # This is a shortcut to implement the essentioal functionality of the tx
        [ self.tx_paths[i].run() for i in range(self.Txantennas) ]

    def write_infile(self,**kwargs):
        for i in range(self.Users):
            if i==0:
                indata=self.iptr_A.data[i].udata.Data.reshape(-1,1)
            else:
                indata=np.r_['1',indata,self.iptr_A.data[i].udata.Data.reshape(-1,1)]
        if self.model=='sv':
            #This adds an iofile to self.iofiles list
            a=verilog_iofile(self,**{'name':'A','data':indata})
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
            self._Z_real_t[i].Data=a.data[:,i*self.Txantennas+0].astype('str').reshape(-1,1)
            self._Z_real_b[i].Data=a.data[:,i*self.Txantennas+1].astype('int').reshape(-1,1)
            self._Z_imag_t[i].Data=a.data[:,i*self.Txantennas+2].astype('str').reshape(-1,1)
            self._Z_imag_b[i].Data=a.data[:,i*self.Txantennas+3].astype('int').reshape(-1,1)

