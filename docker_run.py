#!/usr/bin/env python3

from typing import Optional
from pathlib import Path
import sys
import grp
import subprocess
import argparse

class Color:
    yellow = "\x1b[33m"
    green = "\x1b[32m"
    red = "\x1b[21m"
    bold_red = "\x1b[31;1m"
    bold = "\033[1m"
    uline = "\033[4m"
    reset = "\x1b[0m"

def warn(msg: str):
    sys.stderr.write(f"{Color.bold}WARNING{Color.reset}: {msg}\n")

def get_group_id(group_name: str) -> Optional[int]:
    try:
        group_info = grp.getgrnam(group_name)
    except Exception:
        return None
    return group_info.gr_gid

def get_group_members(group_name: str) -> list[str]:
    if get_group_id(group_name) is None:
        return []
    return grp.getgrnam(group_name).gr_mem

def construct_groups_params(groups: list[str] = ["dialout", "plugdev"]):
    res = " "
    for name in groups:
        id = get_group_id(name)
        if id is None:
            warn(f"Could not find group '{name}' in /etc/group! In order to avoid UART/JTAG connection issues, please add the group manually, set your user as a member and refresh (As a result command 'groups' should print it)")
            continue
        res += f"--group-add {id} "
        
    return res

def main(cmd : Optional[str]):
    container_name = "docker.io/library/mtkcpu:1.0.0"
    interactive = "" if cmd else "-it"
    if not cmd:
        cmd = ""
    else:
        if (not cmd.startswith("sh")) and (not cmd.startswith("bash")):
            cmd = f"sh -c '{cmd}'"

    command = f"""
docker run \
--init --tty \
--net host \
{construct_groups_params()} \
-v {Path(__file__).parent}/sw:/toolchain/sw \
{interactive} {container_name} {cmd}
    """
    print(command)

    subprocess.run(command, shell=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(usage="Runs interactive bash session inside Plumerai-Demo docker container.")
    parser.add_argument("--cmd", type=str)
    main(**vars(parser.parse_args()))