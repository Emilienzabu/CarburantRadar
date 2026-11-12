import unittest
from quality_gate import _validate_steps

BOX={'x':20,'y':30,'width':100,'height':50}
CORE=[{'action':name,'bbox':BOX} for name in ('choose_fuel','locate','results')]

class OnboardingGateV24Tests(unittest.TestCase):
    def test_old_trace(self):
        self.assertEqual(_validate_steps(CORE,(390,844)),CORE)
    def test_guest_and_tutorial(self):
        prefix=[{'action':'continue_without_account','verified':True}, {'action':'skip_tutorial','verified':True}]
        self.assertEqual(_validate_steps(prefix+CORE,(390,844)),CORE)
    def test_tutorial_only(self):
        self.assertEqual(_validate_steps([{'action':'skip_tutorial','verified':True}]+CORE,(390,844)),CORE)
    def test_unverified_onboarding_rejected(self):
        with self.assertRaises(ValueError): _validate_steps([{'action':'skip_tutorial','verified':False}]+CORE,(390,844))
    def test_reordered_onboarding_rejected(self):
        with self.assertRaises(ValueError): _validate_steps([{'action':'skip_tutorial','verified':True},{'action':'continue_without_account','verified':True}]+CORE,(390,844))
    def test_duplicate_onboarding_rejected(self):
        with self.assertRaises(ValueError): _validate_steps([{'action':'skip_tutorial','verified':True}]*2+CORE,(390,844))
    def test_extra_action_rejected(self):
        with self.assertRaises(ValueError): _validate_steps([{'action':'unexpected'}]+CORE,(390,844))
    def test_bad_bbox_rejected(self):
        with self.assertRaises(ValueError): _validate_steps([{'action':'choose_fuel','bbox':{'x':380,'y':0,'width':20,'height':10}}]+CORE[1:],(390,844))

if __name__=='__main__': unittest.main()
