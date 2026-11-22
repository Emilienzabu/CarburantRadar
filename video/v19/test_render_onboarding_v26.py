import unittest
from render_verified import selected_steps

B = {'x':10,'y':20,'width':100,'height':30}
CORE = [{'action': a, 'bbox': B} for a in ('choose_fuel','locate','results')]

class RendererOnboardingV26(unittest.TestCase):
    def test_no_onboarding(self):
        self.assertEqual(selected_steps({'steps':CORE}), CORE)
    def test_guest(self):
        self.assertEqual(selected_steps({'steps':[{'action':'continue_without_account','verified':True}]+CORE}),CORE)
    def test_tutorial(self):
        self.assertEqual(selected_steps({'steps':[{'action':'skip_tutorial','verified':True}]+CORE}),CORE)
    def test_both(self):
        self.assertEqual(selected_steps({'steps':[{'action':'continue_without_account','verified':True},{'action':'skip_tutorial','verified':True}]+CORE}),CORE)
    def test_unverified(self):
        with self.assertRaises(ValueError): selected_steps({'steps':[{'action':'skip_tutorial','verified':False}]+CORE})
    def test_duplicate(self):
        with self.assertRaises(ValueError): selected_steps({'steps':[{'action':'skip_tutorial','verified':True}]*2+CORE})
    def test_wrong_order(self):
        with self.assertRaises(ValueError): selected_steps({'steps':[{'action':'skip_tutorial','verified':True},{'action':'continue_without_account','verified':True}]+CORE})
    def test_extra(self):
        with self.assertRaises(ValueError): selected_steps({'steps':CORE+[{'action':'other'}]})
    def test_reordered(self):
        with self.assertRaises(ValueError): selected_steps({'steps':CORE[::-1]})

if __name__=='__main__':unittest.main()
