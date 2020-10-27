attribute \generator "nMigen"
attribute \top 1
attribute \nmigen.hierarchy "top"
module \top
  attribute \src "./module.py:14"
  wire width 4 input 0 \a
  attribute \src "./module.py:15"
  wire width 4 input 1 \b
  attribute \src "./module.py:16"
  wire width 4 input 2 \c
  attribute \src "./module.py:17"
  wire width 4 output 3 \y
  attribute \src "./module.py:18"
  wire width 6 $1
  attribute \src "./module.py:18"
  wire width 5 $2
  attribute \src "./module.py:18"
  cell $add $3
    parameter \A_SIGNED 0
    parameter \A_WIDTH 4
    parameter \B_SIGNED 0
    parameter \B_WIDTH 4
    parameter \Y_WIDTH 5
    connect \A \a
    connect \B \b
    connect \Y $2
  end
  attribute \src "./module.py:18"
  wire width 6 $4
  attribute \src "./module.py:18"
  cell $add $5
    parameter \A_SIGNED 0
    parameter \A_WIDTH 5
    parameter \B_SIGNED 0
    parameter \B_WIDTH 4
    parameter \Y_WIDTH 6
    connect \A $2
    connect \B \c
    connect \Y $4
  end
  connect $1 $4
  process $group_0
    assign \y 4'0000
    assign { \y } $1 [3:0]
    sync init
  end
end

