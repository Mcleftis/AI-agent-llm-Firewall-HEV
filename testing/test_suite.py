import unittest
import sys
import os
import pandas as pd
import numpy as np

#oliko test

#epeidh eimaste ston fakelo tests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))#os.path.dirname(__file__):fakelos pou einai to arxeio,os.path.join(..., '..'):phgaine ena fakelo pisw,os.path.abspath(...) metatrepei to path se apolyto path


from can_bus_firewall import CANBusFirewall
from stable_baselines3 import PPO 

class TestHybridSystem(unittest.TestCase):

    def setUp(self):
        """Τρέχει ΠΡΙΝ από κάθε τεστ. Προετοιμασία."""
        self.firewall = CANBusFirewall(max_delta=50, max_packets=20, auth_token="SECRET_DRIVER_KEY_2026")
        self.csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'my_working_dataset.csv')

    #security
    def test_firewall_auth_success(self):
        """Ελέγχει αν ο σωστός κωδικός περνάει."""
        self.assertTrue(self.firewall.verify_token("SECRET_DRIVER_KEY_2026"))

    def test_firewall_auth_failure(self):
        """Ελέγχει αν ο λάθος κωδικός κόβεται."""
        self.assertFalse(self.firewall.verify_token("HACKER_123"))

    def test_spoofing_detection(self):
        """Ελέγχει αν πιάνει το απότομο άλμα τιμής (Spoofing)."""
        self.firewall.inspect_packet(0x100, "50.0") #arxikh timh
        is_safe = self.firewall.inspect_packet(0x100, "200.0") #alma
        self.assertFalse(is_safe, "Το Firewall απέτυχε να κόψει το Spoofing!")
    #dataset
    def test_dataset_exists(self):
        """Ελέγχει αν υπάρχει το αρχείο δεδομένων."""
        self.assertTrue(os.path.exists(self.csv_path), "Το dataset δεν βρέθηκε!")

    def test_dataset_columns(self):
        """Ελέγχει αν το dataset έχει τις σωστές στήλες."""
        if os.path.exists(self.csv_path):
            df = pd.read_csv(self.csv_path)
            
            required_cols = [
                'Speed (km/h)', 
                'Acceleration (m/s²)',
                'Engine Power (kW)',              
                'Regenerative Braking Power (kW)' 
            ]
            
            for col in required_cols:
                #elegxoume an yparxei h sthlh me h xwris kena
                found = any(col in c.strip() for c in df.columns)#loop an exei to onoma apo tis sthles, to strip afairei kena apo thn arxh kai apo to telos tou string, elegxei an to string col yparxei mesa sto onoma ths sthlhs
                self.assertTrue(found, f"Λείπει η στήλη {col} από το dataset!")

    #edw einai pou kanoume to "mock", den kanoume load olo ton PPO Agent, tsekaroume an yparxei to arxeio, an eixame kanena arxeio 10GB+, tha hthele pragmatiko mocking
    def test_model_files_exist(self):
        """Ελέγχει αν υπάρχουν τα εκπαιδευμένα μοντέλα."""
        model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'ppo_hev.zip')
        self.assertTrue(os.path.exists(model_path), "Το μοντέλο PPO δεν βρέθηκε!")

if __name__ == '__main__':
    print("SYSTEM DIAGNOSTICS: RUNNING TEST SUITE...")
    unittest.main(verbosity=2)