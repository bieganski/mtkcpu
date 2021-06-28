from mtkcpu.utils.tests.utils import jtag_test, jtag_ocd_examine_test, JtagTestCase, JtagOCDTestCase

JTAG_TESTS = [
    JtagTestCase(),
]

JTAG_OCD_TESTS = [
    JtagOCDTestCase(),
]

# @jtag_ocd_examine_test(JTAG_OCD_TESTS)
# def test_jtag_ocd(_):
#     pass

@jtag_test(JTAG_TESTS)
def test_jtag(_):
    pass


