#!/usr/bin/env python3

from nmigen.vendor.xilinx_7series import *
from nmigen import *


# LVCMOS33 - standardowy pin logiczny o napieciu 3.3V

print("aaa")


# to zwroci obiekt
l0 = platform.request('led', 0)
l0.o.eq(fclk[0])

led / switch



przepinanie nóżek ARMA - duzo syfu


ZYNQ:
// sygnaly z arma, moge ich uzywac dla PL
frst - reset
fclk

ResetSynchronizer - tworzy domene sync? // b z arma wychodzi niesynchronizowany


od tego momentu moge uzywac m.d.sync

z zynq wystają AXI


zamiast jakiejs obecnej zaslepki dajemy do axi swoje sygnaly


mamy dostep do IRQ procka oraz do DMA

EMIO - rozszerzenie IO
ARM ma malo pinów, wiec ma EMIO (ethernet, spi etc)


ARM ma kontroler uart
EMIOUART1{RX/TX}


build:
    play = PynQplatform()
    play.build() # odpala vivado


time analysis::

    intra clock table

design timing summary
50 mhz - 20 ns
WNS ~ 8.5 pozostaly budzet, o tyle da sie skrocic okres zegara
100 mhz bedzie zle


REPORT cell usage


top.bit (ma timestamp)
top.bin (leci na fpga)

ssrv.py ładuje na zynq
