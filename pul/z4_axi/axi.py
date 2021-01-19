from nmigen import *


class AxiInterface:
    def __init__(self, data_width, id_width):
        self.data_width = data_width
        self.id_width = id_width

        self.ar_ready = Signal()
        self.ar_valid = Signal()
        self.ar_burst = Signal(2)
        self.ar_size = Signal(2)
        self.ar_len = Signal(4)
        self.ar_lock = Signal(2)
        self.ar_prot = Signal(3)
        self.ar_cache = Signal(4)
        self.ar_qos = Signal(4)
        self.ar_id = Signal(id_width)
        self.ar_addr = Signal(32)

        self.aw_ready = Signal()
        self.aw_valid = Signal()
        self.aw_burst = Signal(2)
        self.aw_size = Signal(2)
        self.aw_len = Signal(4)
        self.aw_lock = Signal(2)
        self.aw_prot = Signal(3)
        self.aw_cache = Signal(4)
        self.aw_qos = Signal(4)
        self.aw_id = Signal(id_width)
        self.aw_addr = Signal(32)

        self.w_ready = Signal()
        self.w_valid = Signal()
        self.w_last = Signal()
        self.w_id = Signal(id_width)
        self.w_strb = Signal(data_width // 8)
        self.w_data = Signal(data_width)

        self.b_ready = Signal()
        self.b_valid = Signal()
        self.b_id = Signal(id_width)
        self.b_resp = Signal(2)

        self.r_ready = Signal()
        self.r_valid = Signal()
        self.r_last = Signal()
        self.r_id = Signal(id_width)
        self.r_resp = Signal(2)
        self.r_data = Signal(data_width)
