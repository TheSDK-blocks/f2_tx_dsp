# f2_dsp class 
# Last modification by Marko Kosunen, marko.kosunen@aalto.fi, 07.08.2018 17:48
import numpy as np
import pandas as pd
import scipy.signal as sig
import tempfile
import subprocess
import shlex
import time

from thesdk import *
from verilog import *
import signal_generator_802_11n as sg80211n


class f2_tx_dsp(verilog,thesdk):
    def __init__(self,*arg): 
        self.proplist = [ 'Rs', 'Rs_dsp', 'Txbits'];    #properties that can be propagated from parent
        self.Rs = 160e6;                 # sampling frequency
        self.Rs_dsp=20e6
        #These are fixed
        self.Txantennas=4
        self.Txbits=9
        self.Users=4                     #This is currently fixed by implementation
        #Matrix of [Users,time,1]
        self.iptr_A = refptr() 
        self.model='sv';                  #can be set externally, but is not propagated
        self.par= False                  #by default, no parallel processing

        self.queue= []                   #by default, no parallel processing
        self._classfile=os.path.dirname(os.path.realpath(__file__)) + "/"+__name__
        self.DEBUG= False
        if len(arg)>=1:
            parent=arg[0]
            self.copy_propval(parent,self.proplist)
            self.parent =parent;

        self._Z_real_t=[ refptr() for i in range(self.Txantennas) ]
        self._Z_real_b=[ refptr() for i in range(self.Txantennas) ]
        self._Z_imag_t=[ refptr() for i in range(self.Txantennas) ]
        self._Z_imag_b=[ refptr() for i in range(self.Txantennas) ]


        #self._decimated.Value=[refptr() for _ in range(4)]
        #self._index=refptr()
        self.init()
    
    def init(self):
        self.def_verilog()
        self._vlogmodulefiles =list(['clkdiv_n_2_4_8.v', 'AsyncResetReg.v'])

        #Here's how we sim't for the tapeout
        self._vlogparameters=dict([ ('g_Rs_high',self.Rs), ('g_Rs_low',self.Rs_dsp), 
            ('g_Rs_high'          , 16*20.0e6),
            ('g_Rs_low'           , 20.0e6),
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
        else: 
          self.write_infile()
          self.run_verilog()
          self.read_outfile()

    def process_input(self):
        self.print_log({'type':"F", 'msg':"Python model not yet implemented"}) 

    def write_infile(self):
        rndpart=os.path.basename(tempfile.mkstemp()[1])
        if self.model=='sv':
            self._infile=self._vlogsimpath +'/A_' + rndpart +'.txt'
            self._outfile=self._vlogsimpath +'/Z_' + rndpart +'.txt'
        elif self.model=='vhdl':
            pass
        else:
            pass
        try:
          os.remove(self._infile)
        except:
          pass
        for i in range(self.Users):
            if i==0:
                indata=self.iptr_A.Value[i,:,0].reshape(-1,1)
            else:
                indata=np.r_['1',indata,self.iptr_A.Value[i,:,0].reshape(-1,1)]

        fid=open(self._infile,'wb')
        np.savetxt(fid,indata.view(float),fmt='%i', delimiter='\t')
        fid.close()

    def read_outfile(self):
        fid=open(self._outfile,'r')
        fromfile = pd.read_csv(fid,dtype=object,sep='\t')
        fid.close()
        os.remove(self._outfile)
        #Of course it does not work symmetrically with savetxt
        for i in range(self.Txantennas):
            self._Z_real_t[i].Value=fromfile.values[:,i*self.Txantennas+0].astype('str').reshape(-1,1)
            self._Z_real_b[i].Value=fromfile.values[:,i*self.Txantennas+1].astype('int').reshape(-1,1)
            self._Z_imag_t[i].Value=fromfile.values[:,i*self.Txantennas+2].astype('str').reshape(-1,1)
            self._Z_imag_b[i].Value=fromfile.values[:,i*self.Txantennas+3].astype('int').reshape(-1,1)
        print( self._Z_real_t[0].Value)
        print( self._Z_real_b[0].Value)

