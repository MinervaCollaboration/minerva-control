import numpy as np
import ipdb
import pprint


class PID:
    """
    Discrete PID control
    """

    def __init__(self, P=np.array([1.0, 1.0]), 
                       I=np.array([0.0, 0.0]),
                       D=np.array([0.0,0.0]), 
                       Derivator=np.array([0.0, 0.0]),
                       Integrator=np.array([0.0, 0.0]), 
                       Integrator_max=20, 
                       Deadband = 0.0, #0.33''/pixel->.33 pix=0.1 "
                       Correction_max = float("inf")):

        self.Kp=P
        self.Ki=I
        self.Kd=D
        self.Derivator=Derivator
        self.Integrator=Integrator
        self.Integrator_max=Integrator_max
        
        self.deadband = Deadband
        self.Correction_max = Correction_max
        self.set_point=0.0
        self.error=0.0
    def update(self,current_value):
        """
        Calculate PID output value for given reference input and feedback
        """
        self.error = self.set_point - current_value

        for i in range(len(self.error)):
            if np.abs(self.error[i])<self.deadband:
                self.error[i] = 0
                #print "Integrator"
                #print self.Integrator
                #self.Integrator[i] = 0.0
            else:
                self.error[i]= (self.error[i]+
                               np.sign(self.error[i])*(-self.deadband))
        
        self.P_value = self.Kp * self.error
        self.D_value = self.Kd * ( self.error - self.Derivator)
        self.Derivator = self.error

        self.Integrator = self.Integrator + self.error
        
        for i in range(len(self.Integrator)):
            if self.Integrator[i]>self.Integrator_max:
                self.Integrator[i]=self.Integrator_max
            if self.Integrator[i] < -1.0*self.Integrator_max:
                self.Integrator[i]=-1.0*self.Integrator_max

        self.I_value = self.Integrator * self.Ki

        PID = self.P_value + self.I_value + self.D_value
        #for j in range(len(PID)):
        #    if abs(PID[j])>self.Correction_max:
        #        PID[j]=self.Correction_max*np.sign(PID[j])
        if np.linalg.norm(PID)>self.Correction_max:
            PID = PID/np.linalg.norm(PID)*self.Correction_max
        print "PID"
        print PID
        return PID

    def setPoint(self,set_point):
        """
        Initilize the setpoint of PID
        """
        self.set_point = set_point
        self.Integrator=np.array([0.0, 0.0])
        self.Derivator=np.array([0.0, 0.0])

    def setIntegrator(self, Integrator):
        self.Integrator = Integrator

    def setDerivator(self, Derivator):
        self.Derivator = Derivator

    def setKp(self,P):
        self.Kp=P

    def setKi(self,I):
        self.Ki=I

    def setKd(self,D):
        self.Kd=D

    def getPoint(self):
        return self.set_point

    def getError(self):
        return self.error

    def getIntegrator(self):
        return self.Integrator

    def getDerivator(self):
        return self.Derivator
    
    def setDeadband(self, dead):
        self.Deadband = dead
    
    def setImax(self, imax):
        self.Integrator_max = imax


if __name__ == "__main__":
    
    p=PID(P=np.array([3.0,3.0]),
          I=np.array([0.4, 0.4]),
          D=np.array([1.2, 1.2]))
    p.setPoint(np.array([5.0, 5.0]))
    while True:
        valx=float(raw_input("enter a positionx: "))
        valy=float(raw_input("enter a positiony: "))
        val=np.array([valx, valy])
        pid=p.update(val)
        pprint.pprint( pid)
        pprint.pprint (p.__dict__)
