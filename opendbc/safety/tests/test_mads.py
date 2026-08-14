#!/usr/bin/env python3
import unittest

from opendbc.safety.tests.libsafety import libsafety_py

ALT_EXP_ENABLE_MADS = 1024
ALT_EXP_MADS_DISENGAGE_LATERAL_ON_BRAKE = 2048
ALT_EXP_MADS_PAUSE_LATERAL_ON_BRAKE = 4096
ALT_EXP_RESERVED_BIT0 = 1

BUTTON_UNAVAILABLE = -1
BUTTON_NOT_PRESSED = 0
BUTTON_PRESSED = 1

REASON_NONE = 0
REASON_BRAKE = 1
REASON_ACC_MAIN_OFF = 8
REASON_HEARTBEAT_ENGAGED_MISMATCH = 32
REASON_STEERING_DISENGAGE = 64


class TestMads(unittest.TestCase):
  def setUp(self):
    self.safety = libsafety_py.libsafety
    self.safety.set_controls_allowed(False)
    self.safety.mads_set_button_press(BUTTON_UNAVAILABLE)
    self.safety.mads_set_heartbeat_engaged(False)
    self.set_mode(ALT_EXP_ENABLE_MADS)

  def tearDown(self):
    self.safety.mads_set_button_press(BUTTON_UNAVAILABLE)
    self.safety.mads_set_heartbeat_engaged(False)
    self.safety.mads_test_set_alternative_experience(0)

  def set_mode(self, mode):
    self.safety.mads_test_set_alternative_experience(mode)
    self.tick()
    self.assertFalse(self.engaged)

  def tick(self, acc_main=False, op_allowed=False, braking=False, steering_disengage=False, moving=False):
    self.safety.mads_state_update(moving, acc_main, op_allowed, braking, steering_disengage)

  @property
  def engaged(self):
    return self.safety.mads_get_controls_allowed_lateral()

  def engage_via_acc_main(self):
    self.tick(acc_main=True)
    self.assertTrue(self.engaged)

  def test_acc_main_rising_engages(self):
    self.engage_via_acc_main()

  def test_steady_state_does_not_engage(self):
    for _ in range(5):
      self.tick()
      self.assertFalse(self.engaged)

  def test_acc_main_held_does_not_reengage_after_exit(self):
    self.engage_via_acc_main()
    self.safety.mads_test_exit_controls(REASON_STEERING_DISENGAGE)
    self.assertFalse(self.engaged)
    for _ in range(5):
      self.tick(acc_main=True)
      self.assertFalse(self.engaged)

  def test_button_press_engages(self):
    self.safety.mads_set_button_press(BUTTON_PRESSED)
    self.tick()
    self.assertTrue(self.engaged)

  def test_button_not_pressed_does_not_engage(self):
    self.safety.mads_set_button_press(BUTTON_NOT_PRESSED)
    for _ in range(5):
      self.tick()
      self.assertFalse(self.engaged)

  def test_button_held_does_not_reengage_after_exit(self):
    self.safety.mads_set_button_press(BUTTON_PRESSED)
    self.tick()
    self.assertTrue(self.engaged)
    self.safety.mads_test_exit_controls(REASON_STEERING_DISENGAGE)
    for _ in range(5):
      self.tick()
      self.assertFalse(self.engaged)

  def test_op_controls_allowed_rising_engages(self):
    self.tick(op_allowed=True)
    self.assertTrue(self.engaged)

  def test_acc_main_falling_disengages(self):
    self.engage_via_acc_main()
    self.tick(acc_main=False)
    self.assertFalse(self.engaged)
    self.assertEqual(self.safety.mads_get_active_disengage_reason(), REASON_ACC_MAIN_OFF)

  def test_steering_disengage_rising_disengages(self):
    self.engage_via_acc_main()
    self.tick(acc_main=True, steering_disengage=True)
    self.assertFalse(self.engaged)
    self.assertEqual(self.safety.mads_get_active_disengage_reason(), REASON_STEERING_DISENGAGE)

  def test_steering_disengage_held_does_not_disengage_again(self):
    self.engage_via_acc_main()
    self.tick(acc_main=True, steering_disengage=True)
    self.safety.mads_test_set_alternative_experience(ALT_EXP_ENABLE_MADS)
    self.tick(steering_disengage=True)
    self.tick(acc_main=True, steering_disengage=True)
    self.assertTrue(self.engaged)

  def test_disengage_lateral_on_brake(self):
    self.set_mode(ALT_EXP_ENABLE_MADS | ALT_EXP_MADS_DISENGAGE_LATERAL_ON_BRAKE)
    self.engage_via_acc_main()
    self.tick(acc_main=True, braking=True)
    self.assertFalse(self.engaged)
    self.assertEqual(self.safety.mads_get_active_disengage_reason(), REASON_BRAKE)
    self.tick(acc_main=True, braking=False)
    self.assertFalse(self.engaged)

  def test_brake_ignored_without_brake_options(self):
    self.set_mode(ALT_EXP_ENABLE_MADS | ALT_EXP_RESERVED_BIT0)
    self.engage_via_acc_main()
    for _ in range(3):
      self.tick(acc_main=True, braking=True)
      self.assertTrue(self.engaged)
    self.tick(acc_main=True, braking=False)
    self.assertTrue(self.engaged)

  def test_pause_lateral_on_brake_resumes_on_release(self):
    self.set_mode(ALT_EXP_ENABLE_MADS | ALT_EXP_MADS_PAUSE_LATERAL_ON_BRAKE)
    self.engage_via_acc_main()
    self.tick(acc_main=True, braking=True)
    self.assertFalse(self.engaged)
    self.assertEqual(self.safety.mads_get_active_disengage_reason(), REASON_BRAKE)
    self.assertEqual(self.safety.mads_get_pending_disengage_reasons(), REASON_BRAKE)
    self.tick(acc_main=True, braking=False)
    self.assertTrue(self.engaged)
    self.assertEqual(self.safety.mads_get_active_disengage_reason(), REASON_NONE)
    self.assertEqual(self.safety.mads_get_pending_disengage_reasons(), REASON_NONE)

  def test_pause_lateral_on_brake_stays_paused_while_held(self):
    self.set_mode(ALT_EXP_ENABLE_MADS | ALT_EXP_MADS_PAUSE_LATERAL_ON_BRAKE)
    self.engage_via_acc_main()
    self.tick(acc_main=True, braking=True)
    for _ in range(5):
      self.tick(acc_main=True, braking=True)
      self.assertFalse(self.engaged)

  def test_pause_lateral_on_brake_no_resume_after_other_reason(self):
    self.set_mode(ALT_EXP_ENABLE_MADS | ALT_EXP_MADS_PAUSE_LATERAL_ON_BRAKE)
    self.engage_via_acc_main()
    self.tick(acc_main=True, braking=True)
    self.assertFalse(self.engaged)
    self.safety.mads_test_exit_controls(REASON_STEERING_DISENGAGE)
    self.assertEqual(self.safety.mads_get_pending_disengage_reasons(), REASON_BRAKE | REASON_STEERING_DISENGAGE)
    self.tick(acc_main=True, braking=False)
    self.assertFalse(self.engaged)

  def test_disabled_system_never_engages(self):
    self.set_mode(0)
    self.safety.mads_set_button_press(BUTTON_PRESSED)
    for _ in range(5):
      self.tick(acc_main=True, op_allowed=True)
      self.assertFalse(self.engaged)

  def test_enable_bit_required(self):
    self.safety.mads_test_set_alternative_experience(0)
    self.assertFalse(self.safety.mads_get_system_enabled())
    self.safety.mads_test_set_alternative_experience(ALT_EXP_RESERVED_BIT0)
    self.assertFalse(self.safety.mads_get_system_enabled())
    self.safety.mads_test_set_alternative_experience(ALT_EXP_ENABLE_MADS)
    self.assertTrue(self.safety.mads_get_system_enabled())
    self.safety.mads_test_set_alternative_experience(ALT_EXP_ENABLE_MADS | ALT_EXP_RESERVED_BIT0)
    self.assertTrue(self.safety.mads_get_system_enabled())

  def test_heartbeat_mismatch_disengages_after_three(self):
    self.engage_via_acc_main()
    self.safety.mads_set_heartbeat_engaged(False)

    self.safety.mads_heartbeat_engaged_check()
    self.assertEqual(self.safety.mads_get_heartbeat_mismatches(), 1)
    self.assertTrue(self.engaged)

    self.safety.mads_heartbeat_engaged_check()
    self.assertEqual(self.safety.mads_get_heartbeat_mismatches(), 2)
    self.assertTrue(self.engaged)

    self.safety.mads_heartbeat_engaged_check()
    self.assertEqual(self.safety.mads_get_heartbeat_mismatches(), 3)
    self.assertFalse(self.engaged)
    self.assertEqual(self.safety.mads_get_active_disengage_reason(), REASON_HEARTBEAT_ENGAGED_MISMATCH)

  def test_heartbeat_engaged_keeps_mismatches_cleared(self):
    self.engage_via_acc_main()
    self.safety.mads_set_heartbeat_engaged(True)
    for _ in range(5):
      self.safety.mads_heartbeat_engaged_check()
      self.assertEqual(self.safety.mads_get_heartbeat_mismatches(), 0)
      self.assertTrue(self.engaged)

  def test_heartbeat_mismatch_counter_resets(self):
    self.engage_via_acc_main()
    self.safety.mads_set_heartbeat_engaged(False)
    self.safety.mads_heartbeat_engaged_check()
    self.safety.mads_heartbeat_engaged_check()
    self.assertEqual(self.safety.mads_get_heartbeat_mismatches(), 2)
    self.safety.mads_set_heartbeat_engaged(True)
    self.safety.mads_heartbeat_engaged_check()
    self.assertEqual(self.safety.mads_get_heartbeat_mismatches(), 0)
    self.assertTrue(self.engaged)

  def test_heartbeat_not_counted_when_disengaged(self):
    self.safety.mads_set_heartbeat_engaged(False)
    for _ in range(5):
      self.safety.mads_heartbeat_engaged_check()
      self.assertEqual(self.safety.mads_get_heartbeat_mismatches(), 0)


if __name__ == "__main__":
  unittest.main()
