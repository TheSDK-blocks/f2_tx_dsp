# f2_dsp class 
# Last modification by Marko Kosunen, marko.kosunen@aalto.fi, 01.08.2018 17:29
import numpy as np
import scipy.signal as sig
import tempfile
import subprocess
import shlex
import time

from refptr import *
from thesdk import *
from rtl import *
from f2_decimator import *
import signal_generator_802_11n as sg80211n


class f2_rx_dsp(verilog,thesdk):
    def __init__(self,*arg): 
        self.proplist = [ 'Rs', 'Rs_dsp', 'dsp_decimator_scales'];    #properties that can be propagated from parent
        self.Rs = 160e6;                 # sampling frequency
        self.Rs_dsp=20e6
        #These are fixed
        self.Txantennas=1
        self.Users=1
        self.Rxindex=0
        self.Userindex=0
        self.iptr_A = refptr() 
        self.model='sv';                  #can be set externally, but is not propagated
        #self.dsp_decimator_model='py'    #Used only for python model byt can be set for testing
        #self.rtldiscard=50
        #self.rx_output_mode=1
        #self.dspmode='local';              # [ 'local' | 'cpu' ]  
        self.par= False                  #by default, no parallel processing
        self.queue= []                   #by default, no parallel processing
        #self._decimated=refptr()         #signals sampled at rs_dsp
        self._classfile=os.path.dirname(os.path.realpath(__file__)) + "/"+__name__
        self.DEBUG= False
        if len(arg)>=1:
            parent=arg[0]
            self.copy_propval(parent,self.proplist)
            self.parent =parent;

        #Matrix of [1,time,Users]
        self.iptr_A.Value=refptr()

        #self._decimated.Value=[refptr() for _ in range(4)]
        #self._index=refptr()
        self.init()
    
    def init(self):
        self.def_verilog()

        #Currently we do not have a python model for this
        #self.interpolator=[ f2_interpolator() for i in range(self.Txantennas)]
        #for i in range(self.Txantennas):
        #    self.decimator[i].Rs_high=self.Rs
        #    self.decimator[i].Rs_low=self.Rs_dsp
        #    self.decimator[i].model=self.dsp_decimator_model
        #    self.decimator[i].iptr_A=self.iptr_A.Value[i]
        #    self.decimator[i].scales=self.dsp_decimator_scales
        #    self.decimator[i].init()

        #self.mode=self.decimator[0].mode
        self._vlogmodulefiles =list(['clkdiv_n_2_4_8.v'])

        #Here's how we sim't for the tapeout
        self._vlogparameters=dict([ ('g_Rs_high',self.Rs), ('g_Rs_low',self.Rs_dsp), 
            ('g_Rs_high'          = 16*20.0e6),
            ('g_Rs_low'           = 20.0e6),
            ('g_shift'            = 0),
            ('g_scale0'           = 8),
            ('g_scale1'           = 2),
            ('g_scale2'           = 2),
            ('g_scale3'           = 512),
            ('g_cic3shift'        = 4),
            ('g_user_spread_mode' = 0),
            ('g_user_sum_mode'    = 0),
            ('g_user_select_index'= 0),
            ('g_interpolator_mode'= 4),
            ('g_dac_data_mode'   = 6)
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
        #Could use parallel for here
        #[ self.decimator[i].run() for i in range(self.Rxantennas) ]

        #Run decimatiors in parallel
        #Split in two phases: First, get the channel estimates
        # l=0
        # que=[]
        # proc=[]
        # for i in range(self.Rxantennas):
        #     self.decimator[i].init()
        #     que.append(multiprocessing.Queue())
        #     proc.append(multiprocessing.Process(target=self.decimator[i].run, args=(que[l],)))
        #     proc[l].start()
        #     l += 1 
        #         
        # #Collect results for dsps
        # l=0
        # for i in range(self.Rxantennas):
        #     for k in range(self.Users):
        #         self._decimated.Value[k].Value=que[l].get()
        #     proc2[l].join()
        #     l+=1
        
        #Each of the TX's transmit something
        #OBS: We are just trying to verify the already existing RTL now, i.e write an input file and smile.

        ####################
        ### At this point we should add the beamforming and the demodulation
        ### BUT CURRENTLY WE DO NOT:
        ####################

        #self.print_log({'type':'W', 'msg':'Discarded %i zero samples to remove possibble initial transients in symbol sync.' %(self.rtldiscard)})
        ##Array (antennas,time,users) of decimated datsrteams  
        #decimated= [ self.decimator[i]._Z.Value.reshape(-1,1)[self.rtldiscard::,0].reshape(-1,1)@np.ones((1,self.Users)) for i in range(self.Rxantennas)]
        #sumuserstream=np.sum(decimated,0)
        #seluser=[ decimated[i][:,self.Userindex].reshape(-1,1) for i in range(self.Rxantennas)]
        #selrx=[ decimated[self.Rxindex][:,i].reshape(-1,1) for i in range(self.Users)]
        #selrxuser=decimated[self.Rxindex][:,self.Userindex].reshape(-1,1)
        #
        #indexeduserstream= [decimated[k].reshape(-1,1) for k in range(self.Rxantennas)]
        #indexedrxstream=[decimated[:][:][k].reshape(-1,1) for k in range(self.Users)]
        # 
        #if (self.rx_output_mode==0):
        #    self.print_log({'type':'I', 'msg': "Applying RX ouput mode %s - Bypass" %(self.rx_output_mode) })
        #    #Bypass the sampling rate is NOT reduced
        #    for k in range(self.Rxantennas):
        #        self._decimated.Value[k].Value=self.iptr_A.Value[k].Value.reshape(-1,1)
        #elif (self.rx_output_mode==1):
        #    self.print_log({'type':'I', 'msg': "Applying RX ouput mode %s - User %s selected from all RX's" %(self.rx_output_mode, self.Userindex) })
        #    for k in range(self.Rxantennas):
        #        self._decimated.Value[k].Value=seluser[k].reshape(-1,1)
        #elif (self.rx_output_mode==2):
        #    self.print_log({'type':'I', 'msg': "Applying RX ouput mode %s - RX %s selected for all users's" %(self.rx_output_mode, self.Rxindex) })
        #    for k in range(self.Users):
        #        self._decimated.Value[k].Value=selrx[k].reshape(-1,1)
        #elif (self.rx_output_mode==3):
        #    self.print_log({'type':'I', 'msg': "Applying RX ouput mode %s - RX %s and user %s selected to ouput index 0" %(self.rx_output_mode, self.Rxindex, self.Userindex) })
        #    for k in range(self.Users):
        #        if k==0:
        #            self._decimated.Value[k].Value=selrxuser.reshape(-1,1)
        #        else:
        #            self._decimated.Value[k].Value=np.zeros_like(selrxuser.reshape(-1,1))
        #elif (self.rx_output_mode==4):
        #    self.print_log({'type':'I', 'msg': "Applying RX ouput mode %s - User data is streamed out in time-interleaved indexed order from four DSP outputs. Output position index=rxindex" %(self.rx_output_mode) })
        #    for k in range(self.Rxantennas):
        #        self._decimated.Value[k].Value=indexeduserstream[k].reshape(-1,1)
        #        #define here the index stream
        #    self._index.Value=np.mod(np.arange(self._decimated.Value[0].shape[0]),4)
        #elif (self.rx_output_mode==5):
        #    self.print_log({'type':'I', 'msg': "Applying RX ouput mode %s - User data is streamed out in time-interleaved indexed order from four DSP outputs. Output position index=user index" %(self.rx_output_mode) })
        #    for k in range(self.Users):
        #        self._decimated.Value[k].Value=indexedrxstream[k].reshape(-1,1)
        #        #define here the index stream
        #    self._index.Value=np.mod(np.arange(self._decimated.Value[0].shape[0]),4)
        #elif (self.rx_output_mode==6):
        #    self.print_log({'type':'I', 'msg': "Applying RX ouput mode %s - Summed data is streamed out. Output position index is user index" %(self.rx_output_mode) })
        #    for k in range(self.Users):
        #        self._decimated.Value[k].Value=sumuserstream[:,k].reshape(-1,1)
        #else:
        #    #Bypass
        #    self.print_log({'type':'I', 'msg': "Applying RX ouput mode %s - Bypass" %(self.rx_output_mode) })
        #    for k in range(self.Rxantennas):
        #        self._decimated.Value[k].Value=self.iptr_A.Value[k].Value.reshape(-1,1)

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
        for i in range(self.Txantennas):
            if i==0:
                indata=self.iptr_A.Value[0,:,i].Value.reshape(-1,1)
            else:
                indata=np.r_['1',indata,self.iptr_A.Value[0,:,i].Value.reshape(-1,1)]

        fid=open(self._infile,'wb')
        np.savetxt(fid,indata.view(float),fmt='%i', delimiter='\t')
        fid.close()

    def read_outfile(self):
        fid=open(self._outfile,'r')
        fromfile = np.loadtxt(fid,dtype=complex,delimiter='\t')
        #Of course it does not work symmetrically with savetxt
        for i in range(self.Txantennas):
            if i==0:
                out=np.zeros((fromfile.shape[0],int(fromfile.shape[1]/2)),dtype=complex)
                out[:,i]=(fromfile[:,2*i]+1j*fromfile[:,2*i+1]) 
            else:
                out[:,i]=(fromfile[:,2*i]+1j*fromfile[:,2*i+1])
            maximum=np.amax([np.abs(np.real(out[:,i])), np.abs(np.imag(out[:,i]))])
            str="Output signal range is %i" %(maximum)
            self.print_log({'type':'I', 'msg': str})
        fid.close()
        os.remove(self._outfile)
  
