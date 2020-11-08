attribute \generator "nMigen"
attribute \top 1
attribute \nmigen.hierarchy "top"
module \top
  attribute \src "./module.py:7"
  wire width 4 input 0 \a
  attribute \src "./module.py:8"
  wire width 4 input 1 \b
  attribute \src "./module.py:14"
  wire width 8 output 2 \out
  attribute \src "./module.py:14"
  wire width 8 \out$next
  attribute \src "/usr/local/lib/python3.6/dist-packages/nmigen/hdl/ir.py:526"
  wire width 1 input 3 \clk
  attribute \src "/usr/local/lib/python3.6/dist-packages/nmigen/hdl/ir.py:526"
  wire width 1 input 4 \rst
  attribute \src "./module.py:15"
  wire width 4 \counter
  attribute \src "./module.py:15"
  wire width 4 \counter$next
  attribute \src "./module.py:22"
  wire width 2 \fsm_state
  attribute \src "./module.py:22"
  wire width 2 \fsm_state$next
  attribute \src "./module.py:24"
  wire width 5 $1
  attribute \src "./module.py:24"
  wire width 5 $2
  attribute \src "./module.py:24"
  cell $add $3
    parameter \A_SIGNED 0
    parameter \A_WIDTH 4
    parameter \B_SIGNED 0
    parameter \B_WIDTH 1
    parameter \Y_WIDTH 5
    connect \A \counter
    connect \B 1'1
    connect \Y $2
  end
  connect $1 $2
  process $group_0
    assign \counter$next \counter
    attribute \src "./module.py:22"
    switch \fsm_state
      attribute \src "./module.py:23"
      attribute \nmigen.decoding "START/0"
      case 2'00
        assign \counter$next $1 [3:0]
      attribute \src "./module.py:31"
      attribute \nmigen.decoding "LOOP/1"
      case 2'01
      attribute \src "./module.py:40"
      attribute \nmigen.decoding "END/2"
      case 2'10
    end
    attribute \src "/usr/local/lib/python3.6/dist-packages/nmigen/hdl/xfrm.py:519"
    switch \rst
      case 1'1
        assign \counter$next 4'0001
    end
    sync init
      update \counter 4'0001
    sync posedge \clk
      update \counter \counter$next
  end
  attribute \src "./module.py:12"
  wire width 4 \tmp
  process $group_1
    assign \tmp 4'0000
    attribute \src "./module.py:22"
    switch \fsm_state
      attribute \src "./module.py:23"
      attribute \nmigen.decoding "START/0"
      case 2'00
        assign \tmp \a
      attribute \src "./module.py:31"
      attribute \nmigen.decoding "LOOP/1"
      case 2'01
      attribute \src "./module.py:40"
      attribute \nmigen.decoding "END/2"
      case 2'10
    end
    sync init
  end
  attribute \src "./module.py:9"
  wire width 8 \bb
  attribute \src "./module.py:9"
  wire width 8 \bb$next
  attribute \src "./module.py:8"
  wire width 8 $4
  attribute \src "./module.py:8"
  cell $pos $5
    parameter \A_SIGNED 0
    parameter \A_WIDTH 4
    parameter \Y_WIDTH 8
    connect \A \b
    connect \Y $4
  end
  attribute \src "./module.py:33"
  wire width 9 $6
  attribute \src "./module.py:33"
  wire width 9 $7
  attribute \src "./module.py:33"
  cell $sshl $8
    parameter \A_SIGNED 0
    parameter \A_WIDTH 8
    parameter \B_SIGNED 0
    parameter \B_WIDTH 1
    parameter \Y_WIDTH 9
    connect \A \bb
    connect \B 1'1
    connect \Y $7
  end
  connect $6 $7
  process $group_2
    assign \bb$next \bb
    attribute \src "./module.py:22"
    switch \fsm_state
      attribute \src "./module.py:23"
      attribute \nmigen.decoding "START/0"
      case 2'00
        assign \bb$next $4
      attribute \src "./module.py:31"
      attribute \nmigen.decoding "LOOP/1"
      case 2'01
        assign \bb$next $6 [7:0]
      attribute \src "./module.py:40"
      attribute \nmigen.decoding "END/2"
      case 2'10
    end
    attribute \src "/usr/local/lib/python3.6/dist-packages/nmigen/hdl/xfrm.py:519"
    switch \rst
      case 1'1
        assign \bb$next 8'00000000
    end
    sync init
      update \bb 8'00000000
    sync posedge \clk
      update \bb \bb$next
  end
  attribute \src "./module.py:11"
  wire width 1 \en
  attribute \src "./module.py:36"
  wire width 1 $9
  attribute \src "./module.py:36"
  cell $eq $10
    parameter \A_SIGNED 0
    parameter \A_WIDTH 4
    parameter \B_SIGNED 0
    parameter \B_WIDTH 3
    parameter \Y_WIDTH 1
    connect \A \counter
    connect \B 3'100
    connect \Y $9
  end
  process $group_3
    assign \fsm_state$next \fsm_state
    attribute \src "./module.py:22"
    switch \fsm_state
      attribute \src "./module.py:23"
      attribute \nmigen.decoding "START/0"
      case 2'00
        attribute \src "./module.py:27"
        switch { \en }
          attribute \src "./module.py:27"
          case 1'1
            assign \fsm_state$next 2'01
          attribute \src "./module.py:29"
          case
            assign \fsm_state$next 2'00
        end
      attribute \src "./module.py:31"
      attribute \nmigen.decoding "LOOP/1"
      case 2'01
        attribute \src "./module.py:36"
        switch { $9 }
          attribute \src "./module.py:36"
          case 1'1
            assign \fsm_state$next 2'10
          attribute \src "./module.py:38"
          case
            assign \fsm_state$next 2'01
        end
      attribute \src "./module.py:40"
      attribute \nmigen.decoding "END/2"
      case 2'10
    end
    attribute \src "/usr/local/lib/python3.6/dist-packages/nmigen/hdl/xfrm.py:519"
    switch \rst
      case 1'1
        assign \fsm_state$next 2'00
    end
    sync init
      update \fsm_state 2'00
    sync posedge \clk
      update \fsm_state \fsm_state$next
  end
  attribute \src "./module.py:13"
  wire width 1 \bit
  process $group_4
    assign \bit 1'0
    attribute \src "./module.py:22"
    switch \fsm_state
      attribute \src "./module.py:23"
      attribute \nmigen.decoding "START/0"
      case 2'00
      attribute \src "./module.py:31"
      attribute \nmigen.decoding "LOOP/1"
      case 2'01
        assign \bit \tmp [0]
      attribute \src "./module.py:40"
      attribute \nmigen.decoding "END/2"
      case 2'10
    end
    sync init
  end
  attribute \src "./module.py:35"
  wire width 9 $11
  attribute \src "./module.py:35"
  wire width 9 $12
  attribute \src "./module.py:35"
  cell $add $13
    parameter \A_SIGNED 0
    parameter \A_WIDTH 8
    parameter \B_SIGNED 0
    parameter \B_WIDTH 8
    parameter \Y_WIDTH 9
    connect \A \out
    connect \B \bb
    connect \Y $12
  end
  connect $11 $12
  process $group_5
    assign \out$next \out
    attribute \src "./module.py:22"
    switch \fsm_state
      attribute \src "./module.py:23"
      attribute \nmigen.decoding "START/0"
      case 2'00
      attribute \src "./module.py:31"
      attribute \nmigen.decoding "LOOP/1"
      case 2'01
        attribute \src "./module.py:34"
        switch { \bit }
          attribute \src "./module.py:34"
          case 1'1
            assign \out$next $11 [7:0]
        end
      attribute \src "./module.py:40"
      attribute \nmigen.decoding "END/2"
      case 2'10
    end
    attribute \src "/usr/local/lib/python3.6/dist-packages/nmigen/hdl/xfrm.py:519"
    switch \rst
      case 1'1
        assign \out$next 8'00000000
    end
    sync init
      update \out 8'00000000
    sync posedge \clk
      update \out \out$next
  end
  connect \en 1'0
end

