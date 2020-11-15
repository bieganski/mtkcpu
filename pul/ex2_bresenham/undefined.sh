#!/bin/bash

function list_include_item {
  local list="$1"
  local item="$2"
  if [[ $list =~ (^|[[:space:]])"$item"($|[[:space:]]) ]] ; then
    # yes, list include item
    result=0
  else
    result=1
  fi
  return $result
}

defined=`cat bresenham.py | grep Signal | grep -v "#.*Signal" | cut -d \. -f 2 | cut -d = -f 1`

used=`cat  bresenham.py | grep -v "#.*self" | grep self | cut -d \. -f 2 | cut -d = -f 1 | grep -v If | grep -v Elif | grep -v Else | grep -v eq | grep -v "(" | grep -v "+"`

# echo `echo $defined`

# echo `echo $used`



for i in $used; do
	if list_include_item "$defined" "$i"; then
		true # echo "yes"
	else
		echo "$i"
	fi
done
