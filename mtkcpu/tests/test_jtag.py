from mtkcpu.utils.tests.utils import jtag_test, JtagTestCase

JTAG_TESTS = [
    JtagTestCase(),
]

@jtag_test(JTAG_TESTS)
def test_jtag(_):
    pass
