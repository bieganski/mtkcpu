
if { $argc != 1 } {
    puts "Error: usage: ./program.tcl <bitstream>"
    exit
} else {
    set BITSTREAM_FILE [lindex $argv 0]
    puts $BITSTREAM_FILE
}

open_hw_manager

connect_hw_server -url localhost:3121

set target [lindex [get_hw_targets] 0]
current_hw_target $target 
open_hw_target


# Program and Refresh the XC7xxxx Device

set device [lindex [lsearch -inline [get_hw_devices] {xc*}] 0]
current_hw_device $device
refresh_hw_device -update_hw_probes false $device
set_property PROGRAM.FILE "$BITSTREAM_FILE" [lindex [get_hw_devices] 1]

program_hw_devices [lindex [get_hw_devices] 1]
refresh_hw_device $device

# exit
